import re

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models


phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{6,20}$",
    message="请输入有效的手机号。",
)


def normalize_phone(phone):
    return re.sub(r"[\s()\-]", "", phone.strip())


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError("手机号不能为空")

        phone = normalize_phone(phone)
        phone_validator(phone)
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("超级用户必须设置 is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("超级用户必须设置 is_superuser=True")

        return self.create_user(phone, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone = models.CharField(
        "手机号", max_length=21, unique=True, validators=[phone_validator]
    )
    is_active = models.BooleanField("有效", default=True)
    is_staff = models.BooleanField("员工状态", default=False)
    date_joined = models.DateTimeField("加入时间", auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"

    def __str__(self):
        return self.phone

# Create your models here.
