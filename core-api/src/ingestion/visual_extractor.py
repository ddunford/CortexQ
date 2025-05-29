"""
Visual Content Extractor
Extracts and processes images, screenshots, and visual content from documents
"""

import base64
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
import re

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    import io
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL not available - image processing disabled")

try:
    import fitz  # PyMuPDF for PDF image extraction
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available - PDF image extraction disabled")


class VisualContentExtractor:
    """Extract visual content from various document types"""
    
    def __init__(self):
        self.supported_image_formats = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
        self.max_image_size = 5 * 1024 * 1024  # 5MB limit
        self.max_images_per_document = 10
    
    def extract_visual_content(self, content: bytes, content_type: str, filename: str) -> Dict[str, Any]:
        """Extract visual content from document"""
        visual_content = {
            "images": [],
            "screenshots": [],
            "has_visual_content": False,
            "extraction_method": "none"
        }
        
        try:
            if content_type == "application/pdf":
                visual_content = self._extract_pdf_images(content, filename)
            elif content_type == "text/html":
                visual_content = self._extract_html_images(content.decode('utf-8'))
            elif content_type.startswith("image/"):
                visual_content = self._process_single_image(content, content_type, filename)
            elif "word" in content_type or "docx" in content_type:
                visual_content = self._extract_docx_images(content, filename)
            
            visual_content["has_visual_content"] = len(visual_content["images"]) > 0 or len(visual_content["screenshots"]) > 0
            
        except Exception as e:
            logger.error(f"Error extracting visual content from {filename}: {e}")
        
        return visual_content
    
    def _extract_pdf_images(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Extract images from PDF documents"""
        if not PYMUPDF_AVAILABLE:
            return {"images": [], "screenshots": [], "extraction_method": "unavailable"}
        
        try:
            pdf_document = fitz.open(stream=content, filetype="pdf")
            images = []
            screenshots = []
            
            for page_num in range(min(pdf_document.page_count, 20)):  # Limit to first 20 pages
                page = pdf_document[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    if len(images) + len(screenshots) >= self.max_images_per_document:
                        break
                    
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_document, xref)
                        
                        if pix.n - pix.alpha < 4:  # GRAY or RGB
                            img_data = pix.tobytes("png")
                            
                            if len(img_data) <= self.max_image_size:
                                img_base64 = base64.b64encode(img_data).decode('utf-8')
                                
                                # Determine if it's likely a screenshot vs regular image
                                is_screenshot = self._classify_as_screenshot(pix.width, pix.height, filename)
                                
                                image_info = {
                                    "id": f"pdf_img_{page_num}_{img_index}",
                                    "type": "screenshot" if is_screenshot else "image",
                                    "data": f"data:image/png;base64,{img_base64}",
                                    "width": pix.width,
                                    "height": pix.height,
                                    "page": page_num + 1,
                                    "size_bytes": len(img_data),
                                    "alt_text": f"Image from page {page_num + 1} of {filename}"
                                }
                                
                                if is_screenshot:
                                    screenshots.append(image_info)
                                else:
                                    images.append(image_info)
                        
                        pix = None  # Release memory
                        
                    except Exception as e:
                        logger.warning(f"Error extracting image {img_index} from page {page_num}: {e}")
                        continue
            
            pdf_document.close()
            
            return {
                "images": images,
                "screenshots": screenshots,
                "extraction_method": "pymupdf",
                "total_pages_scanned": min(pdf_document.page_count, 20)
            }
            
        except Exception as e:
            logger.error(f"Error extracting PDF images: {e}")
            return {"images": [], "screenshots": [], "extraction_method": "failed"}
    
    def _extract_html_images(self, html_content: str) -> Dict[str, Any]:
        """Extract images from HTML content"""
        images = []
        screenshots = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            img_tags = soup.find_all('img')
            for i, img in enumerate(img_tags[:self.max_images_per_document]):
                src = img.get('src', '')
                alt_text = img.get('alt', '')
                
                # Skip very small images (likely icons)
                width = self._parse_dimension(img.get('width'))
                height = self._parse_dimension(img.get('height'))
                
                if width and height and (width < 50 or height < 50):
                    continue
                
                # Classify as screenshot or regular image
                is_screenshot = self._classify_as_screenshot_from_alt(alt_text, src)
                
                image_info = {
                    "id": f"html_img_{i}",
                    "type": "screenshot" if is_screenshot else "image",
                    "src": src,
                    "alt_text": alt_text,
                    "width": width,
                    "height": height
                }
                
                if is_screenshot:
                    screenshots.append(image_info)
                else:
                    images.append(image_info)
            
            return {
                "images": images,
                "screenshots": screenshots,
                "extraction_method": "html_parsing"
            }
            
        except Exception as e:
            logger.error(f"Error extracting HTML images: {e}")
            return {"images": [], "screenshots": [], "extraction_method": "failed"}
    
    def _extract_docx_images(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Extract images from DOCX documents"""
        try:
            import zipfile
            import io
            
            images = []
            screenshots = []
            
            with zipfile.ZipFile(io.BytesIO(content)) as docx_zip:
                # Look for images in the media folder
                media_files = [f for f in docx_zip.namelist() if f.startswith('word/media/')]
                
                for i, media_file in enumerate(media_files[:self.max_images_per_document]):
                    try:
                        img_data = docx_zip.read(media_file)
                        if len(img_data) <= self.max_image_size:
                            
                            # Determine image format
                            img_format = self._detect_image_format(img_data)
                            if img_format:
                                img_base64 = base64.b64encode(img_data).decode('utf-8')
                                
                                # Try to get image dimensions
                                width, height = self._get_image_dimensions(img_data)
                                
                                # Classify as screenshot or regular image
                                is_screenshot = self._classify_as_screenshot(width, height, media_file)
                                
                                image_info = {
                                    "id": f"docx_img_{i}",
                                    "type": "screenshot" if is_screenshot else "image",
                                    "data": f"data:image/{img_format};base64,{img_base64}",
                                    "width": width,
                                    "height": height,
                                    "size_bytes": len(img_data),
                                    "alt_text": f"Image from {filename}"
                                }
                                
                                if is_screenshot:
                                    screenshots.append(image_info)
                                else:
                                    images.append(image_info)
                    
                    except Exception as e:
                        logger.warning(f"Error extracting image {media_file}: {e}")
                        continue
            
            return {
                "images": images,
                "screenshots": screenshots,
                "extraction_method": "docx_zip"
            }
            
        except Exception as e:
            logger.error(f"Error extracting DOCX images: {e}")
            return {"images": [], "screenshots": [], "extraction_method": "failed"}
    
    def _process_single_image(self, content: bytes, content_type: str, filename: str) -> Dict[str, Any]:
        """Process a single image file"""
        try:
            if len(content) > self.max_image_size:
                return {"images": [], "screenshots": [], "extraction_method": "too_large"}
            
            img_format = content_type.split('/')[-1]
            img_base64 = base64.b64encode(content).decode('utf-8')
            
            # Get image dimensions
            width, height = self._get_image_dimensions(content)
            
            # Classify as screenshot or regular image
            is_screenshot = self._classify_as_screenshot_from_filename(filename)
            
            image_info = {
                "id": "single_image",
                "type": "screenshot" if is_screenshot else "image",
                "data": f"data:{content_type};base64,{img_base64}",
                "width": width,
                "height": height,
                "size_bytes": len(content),
                "alt_text": filename
            }
            
            if is_screenshot:
                return {"images": [], "screenshots": [image_info], "extraction_method": "single_file"}
            else:
                return {"images": [image_info], "screenshots": [], "extraction_method": "single_file"}
            
        except Exception as e:
            logger.error(f"Error processing single image: {e}")
            return {"images": [], "screenshots": [], "extraction_method": "failed"}
    
    def _classify_as_screenshot(self, width: Optional[int], height: Optional[int], filename: str) -> bool:
        """Classify if an image is likely a screenshot"""
        if not width or not height:
            return self._classify_as_screenshot_from_filename(filename)
        
        # Screenshots tend to have certain aspect ratios and sizes
        aspect_ratio = width / height if height > 0 else 1
        
        # Common screenshot indicators
        is_landscape_screenshot = aspect_ratio > 1.2 and width > 800
        is_mobile_screenshot = 0.4 < aspect_ratio < 0.7 and height > 600
        is_ui_screenshot = width > 400 and height > 300
        
        # Check filename for screenshot indicators
        filename_indicates_screenshot = self._classify_as_screenshot_from_filename(filename)
        
        return (is_landscape_screenshot or is_mobile_screenshot or is_ui_screenshot) and filename_indicates_screenshot
    
    def _classify_as_screenshot_from_filename(self, filename: str) -> bool:
        """Check filename for screenshot indicators"""
        filename_lower = filename.lower()
        screenshot_keywords = [
            'screenshot', 'screen', 'capture', 'snap', 'ui', 'interface',
            'dialog', 'window', 'form', 'step', 'guide', 'tutorial'
        ]
        return any(keyword in filename_lower for keyword in screenshot_keywords)
    
    def _classify_as_screenshot_from_alt(self, alt_text: str, src: str) -> bool:
        """Check alt text and src for screenshot indicators"""
        combined_text = f"{alt_text} {src}".lower()
        screenshot_keywords = [
            'screenshot', 'screen', 'capture', 'step', 'guide', 'tutorial',
            'interface', 'dialog', 'window', 'form', 'ui'
        ]
        return any(keyword in combined_text for keyword in screenshot_keywords)
    
    def _get_image_dimensions(self, img_data: bytes) -> tuple[Optional[int], Optional[int]]:
        """Get image dimensions"""
        if not PIL_AVAILABLE:
            return None, None
        
        try:
            with Image.open(io.BytesIO(img_data)) as img:
                return img.width, img.height
        except Exception as e:
            logger.warning(f"Error getting image dimensions: {e}")
            return None, None
    
    def _detect_image_format(self, img_data: bytes) -> Optional[str]:
        """Detect image format from data"""
        if img_data.startswith(b'\x89PNG'):
            return 'png'
        elif img_data.startswith(b'\xFF\xD8\xFF'):
            return 'jpeg'
        elif img_data.startswith(b'GIF87a') or img_data.startswith(b'GIF89a'):
            return 'gif'
        elif img_data.startswith(b'BM'):
            return 'bmp'
        elif img_data.startswith(b'RIFF') and b'WEBP' in img_data[:12]:
            return 'webp'
        return None
    
    def _parse_dimension(self, dim_str: Optional[str]) -> Optional[int]:
        """Parse dimension string to integer"""
        if not dim_str:
            return None
        try:
            # Remove 'px' and other units
            clean_dim = re.sub(r'[^\d]', '', str(dim_str))
            return int(clean_dim) if clean_dim else None
        except (ValueError, TypeError):
            return None 