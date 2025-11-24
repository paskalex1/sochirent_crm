from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import MultipleObjectsReturned


User = get_user_model()


class EmailLoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (css_class + " form-control").strip()

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if not email or not password:
            return cleaned_data

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise forms.ValidationError("Неверный email или пароль.")
        except MultipleObjectsReturned:
            raise forms.ValidationError(
                "Найдено несколько пользователей с таким email. "
                "Обратитесь к администратору."
            )

        auth_user = authenticate(username=user.username, password=password)
        if auth_user is None or not auth_user.is_active:
            raise forms.ValidationError("Неверный email или пароль.")

        cleaned_data["user"] = auth_user
        return cleaned_data
