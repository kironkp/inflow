from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Flowchart, Node


class SignupForm(UserCreationForm):
    """Signup form with a required, unique email so collaborators can be
    looked up by email later (sharing, future password-reset, etc)."""
    email = forms.EmailField(
        required=True,
        label='Email',
        help_text='Used to log in and to receive shared flows.',
    )

    class Meta(UserCreationForm.Meta):
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class FlowchartForm(forms.ModelForm):
    class Meta:
        model = Flowchart
        fields = ['title', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What is this flow for?'}),
        }


class NodeForm(forms.ModelForm):
    new_parent = forms.CharField(
        required=False,
        max_length=120,
        label='Or add a new parent node',
        help_text='Type a label to create a new parent and place this node under it.',
    )

    field_order = ['label', 'subtitle', 'shape', 'branch_label', 'description', 'parent', 'new_parent', 'color', 'tags']

    class Meta:
        model = Node
        fields = ['label', 'subtitle', 'shape', 'branch_label', 'description', 'parent', 'color', 'tags']
        widgets = {
            'subtitle': forms.TextInput(attrs={'placeholder': 'Optional second line (italic)'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'color': forms.TextInput(attrs={'placeholder': '#1B4D5A'}),
            'tags': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, flowchart=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._flowchart = flowchart
        if flowchart is not None:
            qs = Node.objects.filter(flowchart=flowchart)
            if self.instance.pk:
                # Don't allow choosing self or any descendant as parent.
                # Descendant exclusion happens server-side in clean().
                qs = qs.exclude(pk=self.instance.pk)
            self.fields['parent'].queryset = qs
        self.fields['parent'].empty_label = '— Top of flowchart —'

    def clean(self):
        cleaned = super().clean()
        new_name = (cleaned.get('new_parent') or '').strip()
        if new_name and cleaned.get('parent'):
            raise forms.ValidationError(
                'Pick an existing parent or type a new one — not both.'
            )
        cleaned['new_parent'] = new_name

        # Cycle check: chosen parent can't be a descendant of this node.
        parent = cleaned.get('parent')
        if parent and self.instance.pk:
            cur = parent
            seen = set()
            while cur:
                if cur.id == self.instance.pk:
                    raise forms.ValidationError(
                        "Can't choose a descendant as the parent — that would make a loop."
                    )
                if cur.id in seen:
                    break
                seen.add(cur.id)
                cur = cur.parent
        return cleaned

    def save(self, commit=True):
        new_name = self.cleaned_data.get('new_parent', '')
        if new_name and self._flowchart is not None:
            parent, _ = Node.objects.get_or_create(
                flowchart=self._flowchart,
                label=new_name,
                defaults={'shape': 'process'},
            )
            self.instance.parent = parent
        if self._flowchart is not None and not self.instance.flowchart_id:
            self.instance.flowchart = self._flowchart
        return super().save(commit=commit)
