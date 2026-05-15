from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Document, Flowchart, Node, Signature


class SignupForm(UserCreationForm):
    """Email-only signup. The Django User model still has a `username`
    column under the hood — we mirror the email into it so existing
    sharing / login-by-username code paths keep working unchanged.

    Email addresses pass Django's default username validator (it allows
    @ . + - _) so storing them as usernames is safe.
    """
    email = forms.EmailField(
        required=True,
        label='Email',
        help_text='Used to log in and to receive shared flows.',
    )

    class Meta(UserCreationForm.Meta):
        # Drop the username field — we generate it from the email.
        fields = ('email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # UserCreationForm declares username on the class; pop it so it
        # doesn't render and isn't required.
        self.fields.pop('username', None)

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        if User.objects.filter(username__iexact=email).exists():
            # Edge case: someone earlier used an email-shaped username.
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        # Build the user manually because the parent save() relies on the
        # username field being on the form.
        email = self.cleaned_data['email']
        user = User(username=email, email=email)
        user.set_password(self.cleaned_data['password1'])
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

    field_order = ['label', 'subtitle', 'shape', 'branch_label', 'description', 'image', 'parent', 'new_parent', 'color', 'tags']

    class Meta:
        model = Node
        fields = ['label', 'subtitle', 'shape', 'branch_label', 'description', 'image', 'parent', 'color', 'tags']
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


# ---------- Documents (NDA flow) ----------

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'body', 'disclosing_party_name', 'flowchart', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Mutual NDA — VR/AR DAW patent prep'}),
            'body': forms.Textarea(attrs={
                'rows': 18,
                'placeholder': 'Paste the document text here.\n\nLine breaks and blank lines are preserved.',
            }),
            'disclosing_party_name': forms.TextInput(attrs={
                'placeholder': 'Your full legal name (auto-fills the signature block)',
            }),
        }

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit the flowchart picker to the owner's charts.
        if owner is not None:
            self.fields['flowchart'].queryset = Flowchart.objects.filter(user=owner)
            self.fields['flowchart'].empty_label = '— Not linked to a flowchart —'


class SignForm(forms.ModelForm):
    accept = forms.BooleanField(
        required=True,
        label="I have read this document and I agree to be bound by it. My typed name is my electronic signature.",
    )

    class Meta:
        model = Signature
        fields = ['signer_name', 'signer_email', 'typed_signature']
        labels = {
            'signer_name': 'Full legal name',
            'signer_email': 'Email (optional — used for your records)',
            'typed_signature': 'Type your name to sign',
        }
        widgets = {
            'signer_name': forms.TextInput(attrs={'placeholder': 'Jane Q. Lawyer'}),
            'signer_email': forms.EmailInput(attrs={'placeholder': 'jane@firm.com'}),
            'typed_signature': forms.TextInput(attrs={
                'placeholder': 'Type your name here',
                'class': 'signature-input',
                'autocomplete': 'off',
            }),
        }

    def clean(self):
        cleaned = super().clean()
        name = (cleaned.get('signer_name') or '').strip()
        sig = (cleaned.get('typed_signature') or '').strip()
        # Require the typed signature to match the legal name (case-insensitive,
        # ignoring extra whitespace) — this is the "you can't sign as someone
        # else" check that DocuSign and similar services enforce.
        if name and sig and name.lower().split() != sig.lower().split():
            raise forms.ValidationError(
                'Your typed signature must match the legal name you entered above.'
            )
        return cleaned
