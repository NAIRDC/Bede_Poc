from django import forms

class JsonFileUploadForm(forms.Form):
    json_file = forms.FileField(
        label="Upload JSON File",
        required=True,
        help_text="Upload a JSON file containing user data"
    )

class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            "id": "username",
            "class": "relative block w-full text-gray-900 placeholder-gray-500 custom-input sm:text-sm",
            "placeholder": "Username",
            "autocomplete": "username",
        }),
        label="",
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "id": "password",
            "class": "relative block w-full text-gray-900 placeholder-gray-500 custom-input sm:text-sm",
            "placeholder": "Password",
            "autocomplete": "current-password",
        }),
        label="",
    )