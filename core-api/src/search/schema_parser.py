"""
Schema Parser Service for structured data parsing and validation
Implements PRD requirement 3.1: Schema-Aware Indexing for JSON, XML, YAML
"""

import json
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import hashlib
from dataclasses import dataclass
from enum import Enum
import re
from sqlalchemy.orm import Session
from sqlalchemy import text


class SchemaType(str, Enum):
    """Supported schema types"""
    JSON = "json"
    XML = "xml"
    YAML = "yaml"
    CSV = "csv"
    UNKNOWN = "unknown"


@dataclass
class ParsedSchema:
    """Parsed schema result"""
    schema_type: SchemaType
    structure: Dict[str, Any]
    metadata: Dict[str, Any]
    fields: List[Dict[str, Any]]
    content_hash: str
    validation_errors: List[str]
    enriched_data: Dict[str, Any]


class SchemaParser:
    """Parser for structured data with schema awareness"""
    
    def __init__(self):
        self.field_type_patterns = {
            'email': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'url': r'https?://[^\s<>"{}|\\^`[\]]+',
            'phone': r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',
            'date': r'\d{4}-\d{2}-\d{2}',
            'datetime': r'\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}',
            'uuid': r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            'ip_address': r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        }
    
    def parse_content(self, content: str, filename: Optional[str] = None) -> ParsedSchema:
        """
        Parse structured content and return schema information
        
        Args:
            content: Raw content string
            filename: Optional filename for type detection
            
        Returns:
            ParsedSchema object with parsed information
        """
        # Detect schema type
        schema_type = self._detect_schema_type(content, filename)
        
        # Parse based on type
        if schema_type == SchemaType.JSON:
            return self._parse_json(content)
        elif schema_type == SchemaType.XML:
            return self._parse_xml(content)
        elif schema_type == SchemaType.YAML:
            return self._parse_yaml(content)
        elif schema_type == SchemaType.CSV:
            return self._parse_csv(content)
        else:
            return self._parse_unknown(content)
    
    def _detect_schema_type(self, content: str, filename: Optional[str] = None) -> SchemaType:
        """Detect the schema type from content and filename"""
        content = content.strip()
        
        # Check filename extension first
        if filename:
            ext = filename.lower().split('.')[-1]
            if ext == 'json':
                return SchemaType.JSON
            elif ext in ['xml', 'xsd']:
                return SchemaType.XML
            elif ext in ['yaml', 'yml']:
                return SchemaType.YAML
            elif ext == 'csv':
                return SchemaType.CSV
        
        # Check content patterns
        if content.startswith('{') and content.endswith('}'):
            try:
                json.loads(content)
                return SchemaType.JSON
            except:
                pass
        
        if content.startswith('[') and content.endswith(']'):
            try:
                json.loads(content)
                return SchemaType.JSON
            except:
                pass
        
        if content.startswith('<?xml') or content.startswith('<'):
            return SchemaType.XML
        
        # Check for YAML patterns
        if ':' in content and ('\n' in content):
            try:
                yaml.safe_load(content)
                return SchemaType.YAML
            except:
                pass
        
        # Check for CSV patterns (commas with consistent structure)
        lines = content.split('\n')
        if len(lines) > 1:
            first_line_commas = lines[0].count(',')
            if first_line_commas > 0 and all(line.count(',') == first_line_commas for line in lines[:5] if line.strip()):
                return SchemaType.CSV
        
        return SchemaType.UNKNOWN
    
    def _parse_json(self, content: str) -> ParsedSchema:
        """Parse JSON content"""
        validation_errors = []
        try:
            data = json.loads(content)
            
            # Extract schema structure
            structure = self._extract_json_structure(data)
            
            # Extract fields
            fields = self._extract_json_fields(data)
            
            # Generate metadata
            metadata = {
                'type': 'json',
                'size_bytes': len(content),
                'parsed_at': datetime.utcnow().isoformat(),
                'root_type': type(data).__name__,
                'total_fields': len(fields)
            }
            
            # Enrich data
            enriched_data = self._enrich_json_data(data, fields)
            
        except json.JSONDecodeError as e:
            validation_errors.append(f"JSON parsing error: {str(e)}")
            structure = {}
            fields = []
            metadata = {'type': 'json', 'error': str(e)}
            enriched_data = {}
        
        return ParsedSchema(
            schema_type=SchemaType.JSON,
            structure=structure,
            metadata=metadata,
            fields=fields,
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            validation_errors=validation_errors,
            enriched_data=enriched_data
        )
    
    def _parse_xml(self, content: str) -> ParsedSchema:
        """Parse XML content"""
        validation_errors = []
        try:
            root = ET.fromstring(content)
            
            # Extract schema structure
            structure = self._extract_xml_structure(root)
            
            # Extract fields
            fields = self._extract_xml_fields(root)
            
            # Generate metadata
            metadata = {
                'type': 'xml',
                'size_bytes': len(content),
                'parsed_at': datetime.utcnow().isoformat(),
                'root_tag': root.tag,
                'namespaces': list(dict(root.attrib).keys()),
                'total_elements': len(list(root.iter())),
                'total_fields': len(fields)
            }
            
            # Enrich data
            enriched_data = self._enrich_xml_data(root, fields)
            
        except ET.ParseError as e:
            validation_errors.append(f"XML parsing error: {str(e)}")
            structure = {}
            fields = []
            metadata = {'type': 'xml', 'error': str(e)}
            enriched_data = {}
        
        return ParsedSchema(
            schema_type=SchemaType.XML,
            structure=structure,
            metadata=metadata,
            fields=fields,
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            validation_errors=validation_errors,
            enriched_data=enriched_data
        )
    
    def _parse_yaml(self, content: str) -> ParsedSchema:
        """Parse YAML content"""
        validation_errors = []
        try:
            data = yaml.safe_load(content)
            
            # Extract schema structure
            structure = self._extract_yaml_structure(data)
            
            # Extract fields
            fields = self._extract_yaml_fields(data)
            
            # Generate metadata
            metadata = {
                'type': 'yaml',
                'size_bytes': len(content),
                'parsed_at': datetime.utcnow().isoformat(),
                'root_type': type(data).__name__,
                'total_fields': len(fields)
            }
            
            # Enrich data
            enriched_data = self._enrich_yaml_data(data, fields)
            
        except yaml.YAMLError as e:
            validation_errors.append(f"YAML parsing error: {str(e)}")
            structure = {}
            fields = []
            metadata = {'type': 'yaml', 'error': str(e)}
            enriched_data = {}
        
        return ParsedSchema(
            schema_type=SchemaType.YAML,
            structure=structure,
            metadata=metadata,
            fields=fields,
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            validation_errors=validation_errors,
            enriched_data=enriched_data
        )
    
    def _parse_csv(self, content: str) -> ParsedSchema:
        """Parse CSV content"""
        validation_errors = []
        try:
            lines = content.strip().split('\n')
            if not lines:
                raise ValueError("Empty CSV content")
            
            # Parse header and rows
            header = lines[0].split(',')
            rows = [line.split(',') for line in lines[1:] if line.strip()]
            
            # Extract schema structure
            structure = {
                'type': 'table',
                'columns': len(header),
                'rows': len(rows),
                'header': header
            }
            
            # Extract fields with type detection
            fields = self._extract_csv_fields(header, rows)
            
            # Generate metadata
            metadata = {
                'type': 'csv',
                'size_bytes': len(content),
                'parsed_at': datetime.utcnow().isoformat(),
                'columns': len(header),
                'rows': len(rows),
                'total_fields': len(fields)
            }
            
            # Enrich data
            enriched_data = self._enrich_csv_data(header, rows, fields)
            
        except Exception as e:
            validation_errors.append(f"CSV parsing error: {str(e)}")
            structure = {}
            fields = []
            metadata = {'type': 'csv', 'error': str(e)}
            enriched_data = {}
        
        return ParsedSchema(
            schema_type=SchemaType.CSV,
            structure=structure,
            metadata=metadata,
            fields=fields,
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            validation_errors=validation_errors,
            enriched_data=enriched_data
        )
    
    def _parse_unknown(self, content: str) -> ParsedSchema:
        """Parse unknown content type"""
        # Try to extract any structured patterns
        fields = []
        enriched_data = {}
        
        # Look for key-value patterns
        kv_patterns = re.findall(r'(\w+):\s*([^\n]+)', content)
        if kv_patterns:
            fields = [
                {
                    'name': key,
                    'type': self._detect_field_type(value),
                    'sample_value': value,
                    'path': key
                }
                for key, value in kv_patterns[:10]  # Limit to first 10
            ]
            enriched_data = {'key_value_pairs': dict(kv_patterns)}
        
        structure = {
            'type': 'unstructured',
            'patterns_found': len(kv_patterns)
        }
        
        metadata = {
            'type': 'unknown',
            'size_bytes': len(content),
            'parsed_at': datetime.utcnow().isoformat(),
            'total_fields': len(fields)
        }
        
        return ParsedSchema(
            schema_type=SchemaType.UNKNOWN,
            structure=structure,
            metadata=metadata,
            fields=fields,
            content_hash=hashlib.md5(content.encode()).hexdigest(),
            validation_errors=[],
            enriched_data=enriched_data
        )
    
    def _extract_json_structure(self, data: Any, path: str = '') -> Dict[str, Any]:
        """Extract structure from JSON data"""
        if isinstance(data, dict):
            return {
                'type': 'object',
                'keys': list(data.keys()),
                'properties': {
                    key: self._extract_json_structure(value, f"{path}.{key}" if path else key)
                    for key, value in data.items()
                }
            }
        elif isinstance(data, list):
            return {
                'type': 'array',
                'length': len(data),
                'items': self._extract_json_structure(data[0], f"{path}[0]") if data else {'type': 'unknown'}
            }
        else:
            return {
                'type': type(data).__name__,
                'sample': str(data)[:100] if len(str(data)) > 100 else str(data)
            }
    
    def _extract_json_fields(self, data: Any, path: str = '') -> List[Dict[str, Any]]:
        """Extract fields from JSON data"""
        fields = []
        
        if isinstance(data, dict):
            for key, value in data.items():
                current_path = f"{path}.{key}" if path else key
                
                if isinstance(value, (dict, list)):
                    fields.extend(self._extract_json_fields(value, current_path))
                else:
                    fields.append({
                        'name': key,
                        'type': self._detect_field_type(str(value)),
                        'data_type': type(value).__name__,
                        'sample_value': str(value)[:100],
                        'path': current_path
                    })
        
        elif isinstance(data, list):
            for i, item in enumerate(data[:5]):  # Sample first 5 items
                fields.extend(self._extract_json_fields(item, f"{path}[{i}]"))
        
        return fields
    
    def _extract_xml_structure(self, element: ET.Element, path: str = '') -> Dict[str, Any]:
        """Extract structure from XML element"""
        current_path = f"{path}.{element.tag}" if path else element.tag
        
        structure = {
            'type': 'element',
            'tag': element.tag,
            'attributes': dict(element.attrib),
            'text': element.text.strip() if element.text and element.text.strip() else None
        }
        
        if list(element):
            structure['children'] = {}
            for child in element:
                child_tag = child.tag
                if child_tag not in structure['children']:
                    structure['children'][child_tag] = self._extract_xml_structure(child, current_path)
        
        return structure
    
    def _extract_xml_fields(self, element: ET.Element, path: str = '') -> List[Dict[str, Any]]:
        """Extract fields from XML element"""
        fields = []
        current_path = f"{path}.{element.tag}" if path else element.tag
        
        # Add attributes as fields
        for attr_name, attr_value in element.attrib.items():
            fields.append({
                'name': f"{element.tag}@{attr_name}",
                'type': self._detect_field_type(attr_value),
                'data_type': 'attribute',
                'sample_value': attr_value,
                'path': f"{current_path}@{attr_name}"
            })
        
        # Add text content as field if present
        if element.text and element.text.strip():
            fields.append({
                'name': element.tag,
                'type': self._detect_field_type(element.text),
                'data_type': 'text',
                'sample_value': element.text.strip()[:100],
                'path': current_path
            })
        
        # Process child elements
        for child in element:
            fields.extend(self._extract_xml_fields(child, current_path))
        
        return fields
    
    def _extract_yaml_structure(self, data: Any, path: str = '') -> Dict[str, Any]:
        """Extract structure from YAML data (similar to JSON)"""
        return self._extract_json_structure(data, path)
    
    def _extract_yaml_fields(self, data: Any, path: str = '') -> List[Dict[str, Any]]:
        """Extract fields from YAML data (similar to JSON)"""
        return self._extract_json_fields(data, path)
    
    def _extract_csv_fields(self, header: List[str], rows: List[List[str]]) -> List[Dict[str, Any]]:
        """Extract fields from CSV data with type detection"""
        fields = []
        
        for i, column_name in enumerate(header):
            # Sample values from this column
            sample_values = [row[i] if i < len(row) else '' for row in rows[:10]]
            
            # Detect field type based on sample values
            detected_type = self._detect_column_type(sample_values)
            
            fields.append({
                'name': column_name.strip(),
                'type': detected_type,
                'data_type': 'csv_column',
                'sample_value': sample_values[0] if sample_values else '',
                'path': f"column_{i}",
                'column_index': i
            })
        
        return fields
    
    def _detect_field_type(self, value: str) -> str:
        """Detect field type based on value patterns"""
        value = str(value).strip()
        
        for field_type, pattern in self.field_type_patterns.items():
            if re.match(pattern, value):
                return field_type
        
        # Check for numeric types
        try:
            int(value)
            return 'integer'
        except ValueError:
            pass
        
        try:
            float(value)
            return 'float'
        except ValueError:
            pass
        
        # Check for boolean
        if value.lower() in ['true', 'false', 'yes', 'no', '1', '0']:
            return 'boolean'
        
        return 'string'
    
    def _detect_column_type(self, values: List[str]) -> str:
        """Detect column type based on multiple values"""
        if not values:
            return 'string'
        
        # Remove empty values
        non_empty_values = [v for v in values if v.strip()]
        if not non_empty_values:
            return 'string'
        
        # Check if all values match a specific type
        type_counts = {}
        for value in non_empty_values:
            field_type = self._detect_field_type(value)
            type_counts[field_type] = type_counts.get(field_type, 0) + 1
        
        # Return the most common type
        return max(type_counts, key=type_counts.get)
    
    def _enrich_json_data(self, data: Any, fields: List[Dict]) -> Dict[str, Any]:
        """Enrich JSON data with additional insights"""
        return {
            'field_types': {field['name']: field['type'] for field in fields},
            'nested_levels': self._count_nesting_levels(data),
            'total_keys': len(fields)
        }
    
    def _enrich_xml_data(self, element: ET.Element, fields: List[Dict]) -> Dict[str, Any]:
        """Enrich XML data with additional insights"""
        return {
            'field_types': {field['name']: field['type'] for field in fields},
            'total_elements': len(list(element.iter())),
            'namespaces': self._extract_namespaces(element)
        }
    
    def _enrich_yaml_data(self, data: Any, fields: List[Dict]) -> Dict[str, Any]:
        """Enrich YAML data with additional insights"""
        return self._enrich_json_data(data, fields)
    
    def _enrich_csv_data(self, header: List[str], rows: List[List[str]], fields: List[Dict]) -> Dict[str, Any]:
        """Enrich CSV data with additional insights"""
        return {
            'field_types': {field['name']: field['type'] for field in fields},
            'column_stats': self._calculate_csv_stats(header, rows)
        }
    
    def _count_nesting_levels(self, data: Any, current_level: int = 0) -> int:
        """Count maximum nesting levels in data structure"""
        if isinstance(data, dict):
            if not data:
                return current_level
            return max(self._count_nesting_levels(v, current_level + 1) for v in data.values())
        elif isinstance(data, list):
            if not data:
                return current_level
            return max(self._count_nesting_levels(item, current_level + 1) for item in data)
        else:
            return current_level
    
    def _extract_namespaces(self, element: ET.Element) -> List[str]:
        """Extract namespaces from XML element"""
        namespaces = set()
        for elem in element.iter():
            if '}' in elem.tag:
                namespace = elem.tag.split('}')[0] + '}'
                namespaces.add(namespace)
        return list(namespaces)
    
    def _calculate_csv_stats(self, header: List[str], rows: List[List[str]]) -> Dict[str, Any]:
        """Calculate statistics for CSV columns"""
        stats = {}
        for i, column_name in enumerate(header):
            values = [row[i] if i < len(row) else '' for row in rows]
            non_empty = [v for v in values if v.strip()]
            
            stats[column_name] = {
                'total_values': len(values),
                'non_empty_values': len(non_empty),
                'empty_values': len(values) - len(non_empty),
                'unique_values': len(set(non_empty)) if non_empty else 0
            }
        
        return stats
    
    async def store_parsed_schema(self, db: Session, parsed_schema: ParsedSchema, source_id: str):
        """Store parsed schema information in database"""
        try:
            db.execute(
                text("""
                    INSERT INTO parsed_schemas 
                    (id, source_id, schema_type, structure, metadata, fields,
                     content_hash, validation_errors, enriched_data, created_at)
                    VALUES 
                    (gen_random_uuid(), :source_id, :schema_type, :structure, :metadata, :fields,
                     :content_hash, :validation_errors, :enriched_data, :created_at)
                    ON CONFLICT (content_hash) DO UPDATE SET
                    source_id = :source_id, metadata = :metadata, enriched_data = :enriched_data
                """),
                {
                    "source_id": source_id,
                    "schema_type": parsed_schema.schema_type.value,
                    "structure": json.dumps(parsed_schema.structure),
                    "metadata": json.dumps(parsed_schema.metadata),
                    "fields": json.dumps(parsed_schema.fields),
                    "content_hash": parsed_schema.content_hash,
                    "validation_errors": json.dumps(parsed_schema.validation_errors),
                    "enriched_data": json.dumps(parsed_schema.enriched_data),
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            print(f"Error storing parsed schema: {e}")
            db.rollback()


# Global schema parser instance
schema_parser = SchemaParser() 