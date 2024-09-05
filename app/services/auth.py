from app import db
from ..models import User
from flask import jsonify, request
from werkzeug.security import generate_password_hash, check_password_hash
from ..utils.functions import create_http_response
from ..utils.validations import input_validation
from flask_jwt_extended import create_access_token, decode_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from datetime import timedelta
from ..utils.encryption import Encryption
from functools import wraps


@input_validation(
    email={"required": True, "email": True},
    full_name={"required": True},
    password={'required': True, 'min_length': 8}
)
def user_sign_up(request_data: dict) -> jsonify:
    email = request_data.get("email")
    full_name = request_data.get("full_name")
    unhashed_password = request_data.get("password")

    already_existing_user = db.session.execute(db.select(User).where(User.email == email)).scalar()
    if already_existing_user:
        return create_http_response('already existing email', 'failed', 409)

    new_user = User(
        full_name=full_name,
        password=generate_password_hash(unhashed_password, method='pbkdf2:sha256', salt_length=8),
        email=email
    )

    db.session.add(new_user)
    db.session.commit()

    return create_http_response(
        message='Successfully registered',
        status='success',
        http_status=201,
        auth_token=create_auth_token(new_user)
    )


@input_validation(
    email={"required": True, "email": True},
    password={"required": True}
)
def login(request_data: dict) -> jsonify:
    email = request_data.get("email")
    password = request_data.get("password")
    user = db.session.execute(db.select(User).where(User.email == email)).scalar()
    if not user:
        return create_http_response('Invalid email or password', 'failed', 400)

    if not check_password_hash(user.password, password):
        return create_http_response('Invalid email or password', 'failed', 400)
    else:
        return create_http_response(
            message='Login successful',
            status='success',
            http_status=200,
            auth_token=create_auth_token(user)
        )


def create_auth_token(user: User) -> str:
    identity = user.id
    additional_claims = {'full_name': user.full_name}
    access_token = create_access_token(
        identity=identity,
        additional_claims=additional_claims,
        expires_delta=timedelta(hours=24)
    )

    return Encryption.encrypt(access_token)


def authentication_required(f: callable) -> callable:
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return create_http_response("Unauthorized", "failed", 401)

        try:
            decrypted_token = Encryption.decrypt(token)
            decoded_token = decode_token(decrypted_token)
            user_id = decoded_token['identity']
            return f(user_id, *args, **kwargs)

        except ExpiredSignatureError:
            return create_http_response("Token has expired", "Auth Failed", 401)

        except InvalidTokenError:
            return create_http_response("Token is invalid", "Auth Failed", 401)

        except Exception as e:
            return create_http_response(
                f"Auth failed. error: {str(e)}",
                "Auth Failed",
                401
            )

    return decorated_function()

