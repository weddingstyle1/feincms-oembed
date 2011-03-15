from django.core.exceptions import ValidationError
from django.db import models
from django.template.loader import render_to_string
from django.utils import simplejson
from django.utils.http import urlquote, urlencode
from django.utils.translation import ugettext_lazy as _

from urllib import urlopen

from models import LookupCached

class OembedContent(models.Model):
    url = models.URLField(_('URL'), help_text=_('Paste here any URL from supported external websites. F.e. a Youtube Video will be: http://www.youtube.com/watch?v=Nd-vBFJN_2E, a Vimeo Video will be http://vimeo.com/16090755 or a soundcloud audio file: http://soundcloud.com/feinheit/focuszone-radio-spot more sites: http://api.embed.ly/'))
    
    class Meta:
        abstract = True
        verbose_name = _('External content')
        verbose_name_plural = _('External contents')
    
    @classmethod
    def initialize_type(cls, PARAM_CHOICES=None, DIMENSION_CHOICES=None):
        if PARAM_CHOICES is not None:
            cls.add_to_class('parameters', models.CharField(max_length=50,
                                            choices=PARAM_CHOICES, 
                                            default=PARAM_CHOICES[0][0]))
        if DIMENSION_CHOICES is not None:
            cls.add_to_class('dimension', models.CharField(_('dimension'),
                max_length=10, blank=True, null=True, choices=DIMENSION_CHOICES,
                default=DIMENSION_CHOICES[0][0]))
    
    def get_html_from_json(self):
        params = ''
        if 'dimension' in dir(self):
            dimensions = self.dimension.split('x')
            params += urlencode({'maxwidth' : dimensions[0], 'maxheight' : dimensions[1]})
        if 'parameters' in dir(self):
            params += self.parameters
        if len(params) > 0:
            params = '&%s' % params
        
        oohembed_url = 'http://api.embed.ly/1/oembed?url=%s%s' % (urlquote(self.url), params)
        
        lookup, created = LookupCached.objects.get_or_create(url=oohembed_url)
        
        try:
            json = simplejson.loads(lookup.response)
            type = json.get('type')
        except simplejson.JSONDecodeError:
            raise ValidationError('The specified url %s does not respond oembed json' % oohembed_url)
        
        return render_to_string(('external/%s.html' % type, 'external/default.html'), {'response' : json})
    
    def clean(self, *args, **kwargs):
        self.get_html_from_json()
        super(OembedContent, self).save(*args, **kwargs)
    
    def render(self, request, context, **kwargs):
        return self.get_html_from_json()
    