from dataclasses import FrozenInstanceError

import pytest
from pydantic import BaseModel

from fundamentum.infra.http.models import (
	HttpMethod,
	ServiceEndpoint,
	ServiceError,
	ServiceNotFoundError,
	ServiceTimeoutError,
	ServiceUnavailableError,
)


class ExampleRequest(BaseModel):
	customer_id: str


class ExampleResponse(BaseModel):
	id: str
	name: str


def test_http_method_values():
	expected_methods = {
		"GET",
		"POST",
		"PUT",
		"DELETE",
		"PATCH",
		"HEAD",
		"OPTIONS",
	}

	assert set(HttpMethod.__members__.keys()) == expected_methods
	assert {method.value for method in HttpMethod} == expected_methods


def test_service_endpoint_initialization():
	endpoint = ServiceEndpoint(
		service="census",
		path="/api/customers/{customer_id}",
		method=HttpMethod.POST,
		request_model=ExampleRequest,
		response_model=ExampleResponse,
		timeout=5.0,
	)

	assert endpoint.service == "census"
	assert endpoint.path == "/api/customers/{customer_id}"
	assert endpoint.method is HttpMethod.POST
	assert endpoint.request_model is ExampleRequest
	assert endpoint.response_model is ExampleResponse
	assert endpoint.timeout == 5.0


def test_service_endpoint_accepts_list_response_model():
	endpoint = ServiceEndpoint(
		service="census",
		path="/api/customers",
		method=HttpMethod.GET,
		request_model=None,
		response_model=list[ExampleResponse],
	)

	assert endpoint.response_model == list[ExampleResponse]


@pytest.mark.parametrize(
	"field,value,expected_message",
	[
		("service", "", "service cannot be empty"),
		("path", "", "path cannot be empty"),
		("path", "api/customers", "path must start with /"),
	],
)
def test_service_endpoint_validation_errors(field, value, expected_message):
	base_payload = dict(
		service="census",
		path="/api/customers",
		method=HttpMethod.GET,
		request_model=None,
		response_model=ExampleResponse,
	)
	base_payload[field] = value

	with pytest.raises(ValueError, match=expected_message):
		ServiceEndpoint(**base_payload)


def test_service_endpoint_is_immutable():
	endpoint = ServiceEndpoint(
		service="census",
		path="/api/customers",
		method=HttpMethod.GET,
		request_model=None,
		response_model=ExampleResponse,
	)

	with pytest.raises(FrozenInstanceError):
		endpoint.service = "other"


def test_service_error_defaults_are_isolated():
	first_error = ServiceError("boom")
	first_error.details["key"] = "value"

	second_error = ServiceError("another boom")

	assert second_error.details == {}


def test_service_error_attributes():
	details = {"retry": True}

	error = ServiceError(
		"failure",
		endpoint="census.customer_by_id",
		status_code=500,
		details=details,
	)

	assert str(error) == "failure"
	assert error.endpoint == "census.customer_by_id"
	assert error.status_code == 500
	assert error.details is details


def test_service_not_found_error_sets_status_code():
	error = ServiceNotFoundError("not found", endpoint="census.customer_by_id")

	assert error.endpoint == "census.customer_by_id"
	assert error.status_code == 404


def test_service_timeout_error_preserves_endpoint():
	error = ServiceTimeoutError("timeout", endpoint="census.customer_by_id")

	assert error.endpoint == "census.customer_by_id"
	assert error.status_code is None


def test_service_unavailable_error_accepts_status_code():
	error = ServiceUnavailableError(
		"unavailable",
		endpoint="census.customer_by_id",
		status_code=503,
	)

	assert error.endpoint == "census.customer_by_id"
	assert error.status_code == 503
