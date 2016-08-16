import hashlib
import base64


def hash_email(email):
    m = hashlib.sha256()
    m.update(email.encode('utf-8'))

    return base64.urlsafe_b64encode(m.digest())


def user_logging_string(user):
    if user.is_anonymous:
        return 'User(anonymous)'
    return 'User(id={}, role={}, hashed_email={})'.format(user.id, user.role, hash_email(user.email_address))


def user_has_role(user, role):
    try:
        return user['users']['role'] == role
    except (KeyError, TypeError):
        return False


class User():
    def __init__(self, user_id, email_address, supplier_code, supplier_name,
                 locked, active, name, role):
        self.id = user_id
        self.email_address = email_address
        self.name = name
        self.role = role
        self.supplier_code = supplier_code
        self.supplier_name = supplier_name
        self.locked = locked
        self.active = active

    @property
    def is_authenticated(self):
        return self.is_active

    @property
    def is_active(self):
        return self.active and not self.locked

    @property
    def is_locked(self):
        return self.locked

    @property
    def is_anonymous(self):
        return False

    def has_role(self, role):
        return self.role == role

    def has_any_role(self, *roles):
        return any(self.has_role(role) for role in roles)

    def get_id(self):
        try:
            return unicode(self.id)  # python 2
        except NameError:
            return str(self.id)  # python 3

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'emailAddress': self.email_address,
            'supplierCode': self.supplier_code,
            'supplierName': self.supplier_name,
            'locked': self.locked,
        }

    @staticmethod
    def from_json(user_json):
        user = user_json["users"]
        supplier_code = None
        supplier_name = None
        if "supplier" in user:
            supplier_code = user["supplier"]["supplierCode"]
            supplier_name = user["supplier"]["name"]
        return User(
            user_id=user["id"],
            email_address=user['emailAddress'],
            supplier_code=supplier_code,
            supplier_name=supplier_name,
            locked=user.get('locked', False),
            active=user.get('active', True),
            name=user['name'],
            role=user['role']
        )

    @staticmethod
    def load_user(data_api_client, user_id):
        """Load a user from the API and hydrate the User model"""
        user_json = data_api_client.get_user(user_id=int(user_id))

        if user_json:
            user = User.from_json(user_json)
            if user.is_active:
                return user
