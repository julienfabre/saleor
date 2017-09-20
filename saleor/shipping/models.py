from __future__ import absolute_import, unicode_literals
from itertools import groupby
from operator import itemgetter

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.encoding import python_2_unicode_compatible
from django.utils.translation import pgettext_lazy
from django_prices.models import PriceField
from prices import PriceRange, Price
from django_countries import countries


ANY_COUNTRY = ''
ANY_COUNTRY_DISPLAY = pgettext_lazy('Country choice', 'Rest of World')
COUNTRY_CODE_CHOICES = [(ANY_COUNTRY, ANY_COUNTRY_DISPLAY)] + list(countries)


@python_2_unicode_compatible
class ShippingMethod(models.Model):

    name = models.CharField(
        pgettext_lazy('Shipping method field', 'name'),
        max_length=100)
    description = models.TextField(
        pgettext_lazy('Shipping method field', 'description'),
        blank=True, default='')

    class Meta:
        verbose_name = pgettext_lazy('Shipping method model', 'shipping method')
        verbose_name_plural = pgettext_lazy('Shipping method model', 'shipping methods')

    def __str__(self):
        return self.name

    @property
    def countries(self):
        return [str(country) for country in self.price_per_country.all()]

    @property
    def price_range(self):
        prices = [country.price for country in self.price_per_country.all()]
        if prices:
            return PriceRange(min(prices), max(prices))


class ShippingMethodCountryQueryset(models.QuerySet):

    def unique_for_country_code(self, country_code):
        shipping = self.filter(
            Q(country_code=country_code) |
            Q(country_code=ANY_COUNTRY))
        shipping = shipping.order_by('shipping_method_id')
        shipping = shipping.values_list('shipping_method_id', 'id', 'country_code')
        grouped_shipping = groupby(shipping, itemgetter(0))
        any_country = ANY_COUNTRY

        ids = []

        for shipping_method_id, method_values in grouped_shipping:
            method_values = list(method_values)
            # if there is any country choice and specific one remove any country choice
            if len(method_values) == 2:
                method = [val for val in method_values if val[2] != any_country][0]
            else:
                method = method_values[0]
            ids.append(method[1])
        return self.filter(id__in=ids)


@python_2_unicode_compatible
class ShippingMethodCountry(models.Model):

    country_code = models.CharField(
        pgettext_lazy('Shipping method country field', 'country code'),
        choices=COUNTRY_CODE_CHOICES, max_length=2, blank=True, default=ANY_COUNTRY)
    price = PriceField(
        pgettext_lazy('Shipping method country field', 'price'),
        currency=settings.DEFAULT_CURRENCY, max_digits=12, decimal_places=2)
    shipping_method = models.ForeignKey(
        ShippingMethod, related_name='price_per_country',
        verbose_name=pgettext_lazy('Shipping method country field', 'shipping method'),)

    objects = ShippingMethodCountryQueryset.as_manager()

    class Meta:
        unique_together = ('country_code', 'shipping_method')
        verbose_name = pgettext_lazy(
            'Shipping method country model', 'shipping method country')
        verbose_name_plural = pgettext_lazy(
            'Shipping method country model', 'shipping method countries')

    def __str__(self):
        # https://docs.djangoproject.com/en/dev/ref/models/instances/#django.db.models.Model.get_FOO_display  # noqa
        return '%s %s' % (self.shipping_method, self.get_country_code_display())

    def get_total(self, partition=None, shipping_address=None):
        """Calculate shipping price by mass and shipping address if partition is available"""
        if partition:
            # TODO: correct calulation, maybe with data from config file or with foreign key objects
            # We ignore self.country_code and use shipping_address.country instead. We also ignore self.price:
            eu = ['AT', 'BE', 'BG', 'CY', 'CZ', 'DK', 'DE', 'EE', 'ES', 'FI', 'FR', 'GB', 'GR', 'HR', 'HU',
                        'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK']
            import datetime, pytz
            utc = pytz.timezone('UTC')
            t_brexit = datetime.datetime(2019, 4, 1, 0, 0, 0, tzinfo=pytz.utc) # or whatever
            if utc.localize(datetime.datetime.utcnow()) >= t_brexit:
                eu.remove('GB')

            cc = shipping_address.country
            
            # Determine the total mass of the partition:
            mass = 0
            for cart_line in partition:
                mass += cart_line.quantity * cart_line.variant.mass
            # Just an example: 1 €/kg for Germany, 1.5 €/kg for the rest of the EU and 2 €/kg for other countries:
            if cc == 'DE':
                shipping_price = Price(mass, currency=settings.DEFAULT_CURRENCY)
            elif cc in eu:
                shipping_price = Price(1.5 * mass, currency=settings.DEFAULT_CURRENCY)
            else:
                shipping_price = Price(2 * mass, currency=settings.DEFAULT_CURRENCY)
            return shipping_price
        # Standard behaviour just in case in order not to break things 
        else:
            return self.price


class ShippingCountryQueryset(models.QuerySet):

    def unique_for_country_code(self, country_code):
        shipping = self.filter(
            Q(country_code=country_code) |
            Q(country_code=ANY_COUNTRY))
        shipping = shipping.order_by('shipping_method_id')
        shipping = shipping.values_list(
            'shipping_method_id', 'id', 'country_code')
        grouped_shipping = groupby(shipping, itemgetter(0))
        any_country = ANY_COUNTRY

        ids = []

        for shipping_method_id, method_values in grouped_shipping:
            method_values = list(method_values)
            # if there is any country choice and specific one remove any
            # country choice
            if len(method_values) == 2:
                method = [val for val in method_values
                          if val[2] != any_country][0]
            else:
                method = method_values[0]
            ids.append(method[1])
        return self.filter(id__in=ids)
