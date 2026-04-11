from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields + ('email',)


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2.5 rounded-xl bg-earth-100 dark:bg-earth-800 border border-earth-200 dark:border-earth-700 text-earth-800 dark:text-earth-100 focus:ring-2 focus:ring-terra-500 transition outline-none'
            })


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone_number', 'profile_picture', 'bio']
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Tell us about yourself...'}),
            'phone_number': forms.TextInput(attrs={'placeholder': '+91 98765 43210'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'w-full px-4 py-2.5 rounded-xl bg-earth-100 dark:bg-earth-800 border border-earth-200 dark:border-earth-700 text-earth-800 dark:text-earth-100 focus:ring-2 focus:ring-terra-500 transition outline-none'
            })
