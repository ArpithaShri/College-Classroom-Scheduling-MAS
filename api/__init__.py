"""Flask REST API Blueprint and configuration for College Classroom Scheduling System.

Provides API initialization, CORS handling, error handlers, and blueprint registration.
"""

from typing import Any
from flask import Blueprint, jsonify, request
from werkzeug.exceptions import HTTPException

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.after_request
def add_cors_headers(response):
    """Inject CORS headers to allow cross-origin requests from frontend clients."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response


@api_bp.app_errorhandler(HTTPException)
def handle_http_exception(e: HTTPException):
    """Handle standard HTTP exceptions with clean JSON responses."""
    return jsonify({
        "success": False,
        "error": e.description or str(e),
        "code": e.code,
    }), e.code or 500


@api_bp.app_errorhandler(400)
def handle_bad_request(e: Any):
    return jsonify({
        "success": False,
        "error": "Bad request",
        "code": 400,
    }), 400


@api_bp.app_errorhandler(404)
def handle_not_found(e: Any):
    return jsonify({
        "success": False,
        "error": "Resource not found",
        "code": 404,
    }), 404


@api_bp.app_errorhandler(405)
def handle_method_not_allowed(e: Any):
    return jsonify({
        "success": False,
        "error": "Method not allowed",
        "code": 405,
    }), 405


@api_bp.app_errorhandler(409)
def handle_conflict(e: Any):
    return jsonify({
        "success": False,
        "error": "Conflict with current state of resource",
        "code": 409,
    }), 409


@api_bp.app_errorhandler(500)
def handle_internal_server_error(e: Any):
    return jsonify({
        "success": False,
        "error": "An internal server error occurred",
        "code": 500,
    }), 500


# Import routes to register endpoints with blueprint
from . import routes  # noqa: F401, E402
