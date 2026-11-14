# Application storage limit in characters; email-validator also checks protocol lengths.
MAX_EMAIL_LENGTH = 254
MIN_PASSWORD_LENGTH = 15  # NIST minimum recommendation (15 characters)
MAX_PASSWORD_LENGTH = 128  # Application-defined limit (128 characters)
EMAIL_UNIQUE_INDEX = "uq_users_email_lower"  # Case-insensitive email uniqueness
JWT_ALGORITHM = "HS256"
