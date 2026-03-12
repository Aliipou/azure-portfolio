from enum import StrEnum


class DeviceType(StrEnum):
    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    ELECTRICAL = "electrical"
    FLOW = "flow"


class MeasurementStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    VALIDATED = "validated"
    ANOMALY = "anomaly"
    REJECTED = "rejected"


class UserRole(StrEnum):
    ADMIN = "Admin"
    OPERATOR = "Operator"
    VIEWER = "Viewer"
