MAX_EMAIL_LENGTH = 254      # SMTP limit: 256 bytes minus 2 angle brackets; ASCII only (1 char = 1 byte)
MIN_PASSWORD_LENGTH = 15    # NIST minimum recommendation (15 characters)
MAX_PASSWORD_LENGTH = 128   # Application-defined limit (128 characters)
EMAIL_UNIQUE_INDEX = "uq_users_email_lower"  # Case-insensitive email uniqueness
