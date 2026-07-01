# _secret.py (v4) - public verification key only (safe to commit)
# product 3 (3d-models)
PRODUCT_ID = 3
LICENSE_VERSION = 4
_PUB = [40, 184, 161, 118, 180, 79, 199, 16, 75, 245, 142, 43, 184, 1, 165, 234, 198, 204, 149, 103, 36, 204, 165, 17, 177, 152, 173, 218, 242, 161, 105, 198]

def get_public_key():
    return bytes(_PUB)
