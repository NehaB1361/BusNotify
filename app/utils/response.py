"""
Standardized JSON Response helper for BusNotify APIs
Matches Section 45 specification:
Success: { "success": true, "data": ..., "message": "..." }
Error: { "success": false, "error": { "code": "...", "message": "...", "details": ... } }
"""
from flask import jsonify


def api_success(data=None, message="Operation completed successfully", status_code=200):
    response = {
        "success": True,
        "data": data if data is not None else {},
        "message": message
    }
    return jsonify(response), status_code


def api_error(code="ERROR", message="An error occurred", details=None, status_code=400):
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {}
        }
    }
    return jsonify(response), status_code
