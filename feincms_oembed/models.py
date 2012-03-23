from datetime import datetime
import hashlib
import urllib2

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import simplejson
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _


DEFAULT_MAX_AGE = 7 * 24 * 60 * 60 # Cache lookups for a week


def oembed_provider(url, kwargs):
    kwargs['url'] = url
    return 'http://api.embed.ly/1/oembed?%s' % urlencode(kwargs)

if getattr(settings, 'OEMBED_PROVIDER', None):
    from feincms.utils import get_object
    oembed_provider = get_object(settings.OEMBED_PROVIDER)


class CachedLookupManager(models.Manager):
    def get_by_url(self, url, max_age=DEFAULT_MAX_AGE):
        lookup, created = self.get_or_create(
            hash=hashlib.sha1(url).hexdigest(),
            max_age_seconds=max_age,
            defaults={
                'url': url,
                })

        if created:
            lookup.clean()
            lookup.save()

        return lookup

    def request(self, url, max_age=DEFAULT_MAX_AGE):
        return self.get_by_url(url, max_age).response

    def oembed(self, url, max_age=DEFAULT_MAX_AGE, **kwargs):
        lookup = self.get_by_url(
            oembed_provider(url, kwargs),
            max_age=max_age)
        response = simplejson.loads(lookup.response)
        try:
            response['updated'] = lookup.modified
        except AttributeError:
            pass
        return response


class CachedLookup(models.Model):
    hash = models.CharField(_('hash'), max_length=40, unique=True,
        help_text=_('SHA-1 hash of the URL.'))
    url = models.URLField(_('URL'), verify_exists=False, max_length=1000)
    _response = models.TextField(blank=True, null=True)
    _httpstatus = models.PositiveIntegerField(blank=True, null=True)

    max_age_seconds = models.PositiveIntegerField(_('Max. age in seconds'),
        default=DEFAULT_MAX_AGE)

    created = models.DateTimeField(_('created'), auto_now_add=True)
    modified = models.DateTimeField(_('modified'), auto_now=True)

    class Meta:
        verbose_name = _('cached lookup')
        verbose_name_plural = _('cached lookups')

    objects = CachedLookupManager()

    @property
    def response(self):
        delta = datetime.now() - self.modified

        if delta.seconds > self.max_age_seconds:
            self.clean()
            self.save()

        # http responses are always ascii. but django decodes the ascii bytestring
        # during saving. so we have to reencode, sometimes. (after the data was written to the db)
        response = self._response
        if type(response) == unicode:
            response = response.encode('utf-8')

        return response

    def clean(self, *args, **kwargs):
        try:
            request = urllib2.urlopen(self.url)
        except urllib2.URLError as e:
            raise ValidationError(u'This URL cannot be requested: %s' % self.url, e)

        raw = request.read()

        try:
            decoded = raw.decode('utf-8')
        except UnicodeDecodeError:
            decoded = raw.decode('iso8859-1')
        self._response = decoded
        self._httpstatus = request.getcode()

    def __unicode__(self):
        return self.url
