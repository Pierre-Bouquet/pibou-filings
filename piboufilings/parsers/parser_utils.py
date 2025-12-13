"""
Lightweight helpers for parser validation.
"""

import re
from typing import Dict, Any


def validate_filing_content(content: str) -> Dict[str, Any]:
    """
    Quickly validate and summarize raw filing content before parsing.
    
    Args:
        content: Raw filing text.
        
    Returns:
        Dict with validation metadata used by downstream logging.
    """
    validation_result = {
        'is_valid_sec_filing': False,
        'form_type': None,
        'accession_number': None,
        'cik': None,
        'company_name': None,
        'filing_date': None,
        'has_xml_data': False,
        'has_html_data': False,
        'file_size': len(content),
        'supported': False
    }
    
    try:
        if 'SEC-HEADER' in content or 'ACCESSION NUMBER' in content:
            validation_result['is_valid_sec_filing'] = True
        
        form_match = re.search(r"CONFORMED SUBMISSION TYPE:\s+([\w\-]+)", content)
        if form_match:
            form_type = form_match.group(1)
            validation_result['form_type'] = form_type
            validation_result['supported'] = any(
                marker in form_type.upper() for marker in ('13F', 'NPORT')
            )
        
        acc_match = re.search(r"ACCESSION NUMBER:\s+([\d\-]+)", content)
        if acc_match:
            validation_result['accession_number'] = acc_match.group(1)
        
        cik_match = re.search(r"CENTRAL INDEX KEY:\s+(\d+)", content)
        if cik_match:
            validation_result['cik'] = cik_match.group(1)
        
        company_match = re.search(r"COMPANY CONFORMED NAME:\s+(.+)", content)
        if company_match:
            validation_result['company_name'] = company_match.group(1).strip()
        
        date_match = re.search(r"FILED AS OF DATE:\s+(\d+)", content)
        if date_match:
            validation_result['filing_date'] = date_match.group(1)
        
        validation_result['has_xml_data'] = bool(re.search(r'<XML>.*?</XML>', content, re.DOTALL))
        validation_result['has_html_data'] = bool(re.search(r'<TABLE|<HTML', content, re.IGNORECASE))
        
    except Exception as e:
        validation_result['error'] = str(e)
    
    return validation_result
