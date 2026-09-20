DRAFT FOR COUNSEL REVIEW — NOT PUBLISHED

# Security Overview — draft for counsel/customer review
The system uses salted password hashes, expiring revocable sessions, account-owned
records, hashed API keys, production shared quotas, restricted diagnostics and
security headers. Browser tokens are memory-only by default; optional HttpOnly
cookies need deployment/browser validation. No security certification, independent
penetration-test result, or “bank-grade” claim is made.
Database encryption, backup durability, restore timing and production access controls
depend on configured infrastructure and remain unverified. The security.txt endpoint
is inactive until a real contact and future expiry are configured. Report issues
through that published channel once activated. See SECURITY_ARCHITECTURE for precise
implementation and known gaps; this overview is not a guarantee against incidents.
