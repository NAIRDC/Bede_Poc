from django import forms

class JsonFileUploadForm(forms.Form):
    json_file = forms.FileField(
        label="Upload JSON File",
        required=True,
        help_text="Upload a JSON file containing user data"
    )
