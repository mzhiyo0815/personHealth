from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    ReadOnlyPasswordHashField,
    UserCreationForm,
)

from .models import User, normalize_phone, phone_validator


class RegistrationForm(UserCreationForm):
    phone = forms.CharField(
        label="手机号",
        max_length=32,
        widget=forms.TextInput(attrs={"inputmode": "tel", "autocomplete": "tel"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("phone",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "密码"
        self.fields["password1"].help_text = "至少 8 位，不能是常见密码或纯数字。"
        self.fields["password2"].label = "确认密码"
        self.fields["password2"].help_text = "请再次输入相同密码。"

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        phone_validator(phone)
        return phone


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(label="密码")

    class Meta:
        model = User
        fields = "__all__"

    def clean_password(self):
        return self.initial["password"]

    def clean_phone(self):
        phone = normalize_phone(self.cleaned_data["phone"])
        phone_validator(phone)
        return phone


class PhoneAuthenticationForm(AuthenticationForm):
    error_messages = {
        "invalid_login": "手机号或密码不正确，请重试。",
        "inactive": "手机号或密码不正确，请重试。",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.fields["username"].label = "手机号"
        self.fields["username"].widget.attrs["inputmode"] = "tel"
        self.fields["password"].label = "密码"

    def clean_username(self):
        return normalize_phone(self.cleaned_data["username"])
