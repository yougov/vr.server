import re

from jaraco.functools import pass_none, compose
from django import forms
from django.conf import settings
from django.contrib.auth import authenticate

import yaml

from vr.server import models
from .utils import validate_xmlrpc


def yaml_load(yaml_str):
    try:
        return yaml.safe_load(yaml_str)
    except Exception:
        raise forms.ValidationError("Invalid YAML")


try_load = pass_none(compose(validate_xmlrpc, yaml_load))


class ConfigIngredientForm(forms.ModelForm):
    class Meta:
        model = models.ConfigIngredient
        exclude = []

    class Media:
        js = (
            'js/jquery.textarea.min.js',
        )

    def clean_config_yaml(self):
        return try_load(self.cleaned_data.get('config_yaml', None))

    def clean_env_yaml(self):
        return try_load(self.cleaned_data.get('env_yaml', None))


class BuildForm(forms.Form):

    app_id = forms.ChoiceField(choices=[], label='App')
    tag = forms.CharField()

    def __init__(self, *args, **kwargs):
        super(BuildForm, self).__init__(*args, **kwargs)
        choices = [(a.id, a) for a in models.App.objects.all()]
        self.fields['app_id'].choices = choices
        self.fields['app_id'].widget.attrs.update(autofocus='')


class BuildUploadForm(forms.ModelForm):
    class Meta:
        model = models.Build
        exclude = []


class SquadForm(forms.ModelForm):
    class Meta:
        model = models.Squad
        exclude = []


class HostForm(forms.ModelForm):
    class Meta:
        model = models.Host
        exclude = []


class ReleaseForm(forms.ModelForm):
    class Meta:
        model = models.Release
        exclude = ['hash']


class StackForm(forms.ModelForm):
    build_now = forms.BooleanField(initial=True)

    class Meta:
        model = models.OSStack
        exclude = []


class DeploymentForm(forms.Form):
    app = forms.ChoiceField(
        choices=[], help_text="Choose one so we can fill the release combo")
    release_id = forms.ChoiceField(choices=[], label='Release')
    # TODO: proc should be a drop down of the procs available for a given
    # release.  But I guess we can't narrow that down until a release is
    # picked.
    proc = forms.CharField(max_length=50)

    config_name = forms.CharField(help_text=models.config_name_help)

    hostname = forms.ChoiceField(choices=[])
    port = forms.IntegerField()

    def __init__(self, *args, **kwargs):
        super(DeploymentForm, self).__init__(*args, **kwargs)
        self.fields['app'].choices = [('', '----')] + \
            [(app.id, app.name) for app in models.App.objects.all()]
        if 'app' in self.data and self.data['app']:
            releases = models.Release.objects.filter(
                build__app__id=self.data['app'],
            )
            self.fields['release_id'].choices = [
                (release.id, release.get_name())
                for release in releases
            ]
        self.fields['hostname'].choices = \
            [(h.name, h.name) for h in models.Host.objects.filter(active=True)]

    class Media:
        js = (
            'js/fill_releases.js',
        )


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        self.user = authenticate(**self.cleaned_data)
        if not self.user:
            raise forms.ValidationError('Bad username or password')
        return self.cleaned_data


class SwarmForm(forms.Form):
    """
    Form for creating or updating a swarm.
    """
    app_id = forms.ChoiceField(choices=[], label='App')
    tag = forms.CharField(max_length=50)
    config_name = forms.RegexField(
        # At least 1 char, filesystem-safe
        regex=re.compile(r'^[a-zA-Z0-9_]{1,}$'),
        max_length=50,
        help_text=models.config_name_help)
    config_yaml = forms.CharField(
        required=False,
        widget=forms.widgets.Textarea(attrs={'class': 'codearea'}))
    env_yaml = forms.CharField(
        required=False,
        widget=forms.widgets.Textarea(attrs={'class': 'codearea'}))
    volumes = forms.CharField(
        required=False,
        widget=forms.widgets.Textarea(attrs={'class': 'codearea'}))
    run_as = forms.CharField(max_length=32, required=False)
    mem_limit = forms.CharField(max_length=32, required=False,
                                label='Memory',
                                help_text=models.mem_limit_help)
    memsw_limit = forms.CharField(max_length=32, required=False,
                                  label='Memory + Swap',
                                  help_text=models.memsw_limit_help)
    proc_name = forms.CharField(max_length=50)
    squad_id = forms.ChoiceField(choices=[], label='Squad')
    size = forms.IntegerField()
    pool = forms.CharField(max_length=50, required=False)

    balancer_help = "Required if a pool is specified."
    balancer = forms.ChoiceField(choices=[], label='Balancer', required=False,
                                 help_text=balancer_help)

    config_ingredients = forms.ModelMultipleChoiceField(
        queryset=models.ConfigIngredient.objects.all(), required=False)

    def __init__(self, data, *args, **kwargs):
        if 'instance' in kwargs:
            # We get the 'initial' keyword argument or initialize it
            # as a dict if it didn't exist.
            initial = kwargs.setdefault('initial', {})
            # The widget for a ModelMultipleChoiceField expects
            # a list of primary key for the selected data.
            initial['config_ingredients'] = [
                c.pk for c in kwargs['instance'].configingredient_set.all()]

        super(SwarmForm, self).__init__(data, *args, **kwargs)
        self.fields['squad_id'].choices = [(s.id, s) for s in
                                           models.Squad.objects.all()]
        self.fields['app_id'].choices = [(a.id, a) for a in
                                         models.App.objects.all()]
        self.fields['balancer'].choices = [('', '-------')] + [
            (b, b) for b in settings.BALANCERS]

    def clean(self):
        data = super(SwarmForm, self).clean()
        if data['pool'] and not data['balancer']:
            raise forms.ValidationError('Swarms that specify a pool must '
                                        'specify a balancer')
        return data

    def clean_tag(self):
        # Tag becomes part of a filename/dirname. So, / and NUL are invalid.
        invalid_in_filename = re.compile(r'[/\x00]')

        # https://www.mercurial-scm.org/wiki/Tag
        invalid_in_hg = re.compile(r'[:\r\n]')

        # http://git-scm.com/docs/git-check-ref-format
        invalid_in_git = re.compile(r'[ ~^:?*\[\\]')

        tag = self.cleaned_data.get('tag')
        if tag and invalid_in_filename.search(tag) \
                or invalid_in_hg.search(tag) \
                or invalid_in_git.search(tag):
            raise forms.ValidationError('Invalid tag name %s' % tag)
        return tag

    def save(self):
        instance = super(SwarmForm, self).save()
        instance.configingredient_set.clear()
        for ing in self.cleaned_data['config_ingredients']:
            instance.configingredient_set.add(ing)
        return instance

    def clean_config_yaml(self):
        return try_load(self.cleaned_data.get('config_yaml', None))

    def clean_env_yaml(self):
        return try_load(self.cleaned_data.get('env_yaml', None))
