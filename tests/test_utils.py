from __future__ import unicode_literals

from django.conf.urls import url
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import six

import rest_framework.utils.model_meta
from rest_framework.compat import _resolve_model
from rest_framework.routers import SimpleRouter
from rest_framework.serializers import ModelSerializer
from rest_framework.utils import json
from rest_framework.utils.breadcrumbs import get_breadcrumbs
from rest_framework.utils.urls import remove_query_param, replace_query_param
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from tests.models import BasicModel


class Root(APIView):
    pass


class ResourceRoot(APIView):
    pass


class ResourceInstance(APIView):
    pass


class NestedResourceRoot(APIView):
    pass


class NestedResourceInstance(APIView):
    pass


class CustomNameResourceInstance(APIView):
    def get_view_name(self):
        return "Foo"


class ResourceViewSet(ModelViewSet):
    serializer_class = ModelSerializer
    queryset = BasicModel.objects.all()


router = SimpleRouter()
router.register(r'resources', ResourceViewSet)
urlpatterns = [
    url(r'^$', Root.as_view()),
    url(r'^resource/$', ResourceRoot.as_view()),
    url(r'^resource/customname$', CustomNameResourceInstance.as_view()),
    url(r'^resource/(?P<key>[0-9]+)$', ResourceInstance.as_view()),
    url(r'^resource/(?P<key>[0-9]+)/$', NestedResourceRoot.as_view()),
    url(r'^resource/(?P<key>[0-9]+)/(?P<other>[A-Za-z]+)$', NestedResourceInstance.as_view()),
]
urlpatterns += router.urls


@override_settings(ROOT_URLCONF='tests.test_utils')
class BreadcrumbTests(TestCase):
    """
    Tests the breadcrumb functionality used by the HTML renderer.
    """
    def test_root_breadcrumbs(self):
        url = '/'
        assert get_breadcrumbs(url) == [('Root', '/')]

    def test_resource_root_breadcrumbs(self):
        url = '/resource/'
        assert get_breadcrumbs(url) == [
            ('Root', '/'), ('Resource Root', '/resource/')
        ]

    def test_resource_instance_breadcrumbs(self):
        url = '/resource/123'
        assert get_breadcrumbs(url) == [
            ('Root', '/'),
            ('Resource Root', '/resource/'),
            ('Resource Instance', '/resource/123')
        ]

    def test_resource_instance_customname_breadcrumbs(self):
        url = '/resource/customname'
        assert get_breadcrumbs(url) == [
            ('Root', '/'),
            ('Resource Root', '/resource/'),
            ('Foo', '/resource/customname')
        ]

    def test_nested_resource_breadcrumbs(self):
        url = '/resource/123/'
        assert get_breadcrumbs(url) == [
            ('Root', '/'),
            ('Resource Root', '/resource/'),
            ('Resource Instance', '/resource/123'),
            ('Nested Resource Root', '/resource/123/')
        ]

    def test_nested_resource_instance_breadcrumbs(self):
        url = '/resource/123/abc'
        assert get_breadcrumbs(url) == [
            ('Root', '/'),
            ('Resource Root', '/resource/'),
            ('Resource Instance', '/resource/123'),
            ('Nested Resource Root', '/resource/123/'),
            ('Nested Resource Instance', '/resource/123/abc')
        ]

    def test_broken_url_breadcrumbs_handled_gracefully(self):
        url = '/foobar'
        assert get_breadcrumbs(url) == [('Root', '/')]

    def test_modelviewset_resource_instance_breadcrumbs(self):
        url = '/resources/1/'
        assert get_breadcrumbs(url) == [
            ('Root', '/'),
            ('Resource List', '/resources/'),
            ('Resource Instance', '/resources/1/')
        ]


class ResolveModelTests(TestCase):
    """
    `_resolve_model` should return a Django model class given the
    provided argument is a Django model class itself, or a properly
    formatted string representation of one.
    """
    def test_resolve_django_model(self):
        resolved_model = _resolve_model(BasicModel)
        assert resolved_model == BasicModel

    def test_resolve_string_representation(self):
        resolved_model = _resolve_model('tests.BasicModel')
        assert resolved_model == BasicModel

    def test_resolve_unicode_representation(self):
        resolved_model = _resolve_model(six.text_type('tests.BasicModel'))
        assert resolved_model == BasicModel

    def test_resolve_non_django_model(self):
        with self.assertRaises(ValueError):
            _resolve_model(TestCase)

    def test_resolve_improper_string_representation(self):
        with self.assertRaises(ValueError):
            _resolve_model('BasicModel')


class ResolveModelWithPatchedDjangoTests(TestCase):
    """
    Test coverage for when Django's `get_model` returns `None`.

    Under certain circumstances Django may return `None` with `get_model`:
    http://git.io/get-model-source

    It usually happens with circular imports so it is important that DRF
    excepts early, otherwise fault happens downstream and is much more
    difficult to debug.

    """

    def setUp(self):
        """Monkeypatch get_model."""
        self.get_model = rest_framework.compat.apps.get_model

        def get_model(app_label, model_name):
            return None

        rest_framework.compat.apps.get_model = get_model

    def tearDown(self):
        """Revert monkeypatching."""
        rest_framework.compat.apps.get_model = self.get_model

    def test_blows_up_if_model_does_not_resolve(self):
        with self.assertRaises(ImproperlyConfigured):
            _resolve_model('tests.BasicModel')


class JsonFloatTests(TestCase):
    """
    Internaly, wrapped json functions should adhere to strict float handling
    """

    def test_dumps(self):
        with self.assertRaises(ValueError):
            json.dumps(float('inf'))

        with self.assertRaises(ValueError):
            json.dumps(float('nan'))

    def test_loads(self):
        with self.assertRaises(ValueError):
            json.loads("Infinity")

        with self.assertRaises(ValueError):
            json.loads("NaN")


@override_settings(STRICT_JSON=False)
class NonStrictJsonFloatTests(JsonFloatTests):
    """
    'STRICT_JSON = False' should not somehow affect internal json behavior
    """


class UrlsReplaceQueryParamTests(TestCase):
    """
    Tests the replace_query_param functionality.
    """
    def test_valid_unicode_preserved(self):
        # Encoded string: '查询'
        q = '/?q=%E6%9F%A5%E8%AF%A2'
        new_key = 'page'
        new_value = 2
        value = '%E6%9F%A5%E8%AF%A2'

        assert new_key in replace_query_param(q, new_key, new_value)
        assert value in replace_query_param(q, new_key, new_value)

    def test_valid_unicode_replaced(self):
        q = '/?page=1'
        value = '1'
        new_key = 'q'
        new_value = '%E6%9F%A5%E8%AF%A2'

        assert new_key in replace_query_param(q, new_key, new_value)
        assert value in replace_query_param(q, new_key, new_value)

    def test_invalid_unicode(self):
        # Encoded string: '��<script>alert(313)</script>=1'
        q = '/e/?%FF%FE%3C%73%63%72%69%70%74%3E%61%6C%65%72%74%28%33%31%33%29%3C%2F%73%63%72%69%70%74%3E=1'
        key = 'from'
        value = 'login'

        assert key in replace_query_param(q, key, value)


class UrlsRemoveQueryParamTests(TestCase):
    """
    Tests the remove_query_param functionality.
    """
    def test_valid_unicode_preserved(self):
        q = '/?q=%E6%9F%A5%E8%AF%A2'
        new_key = 'page'
        new_value = 2
        value = '%E6%9F%A5%E8%AF%A2'

        assert new_key in replace_query_param(q, new_key, new_value)
        assert value in replace_query_param(q, new_key, new_value)

    def test_valid_unicode_removed(self):
        q = '/?page=2345&q=%E6%9F%A5%E8%AF%A2'
        key = 'page'
        value = '2345'
        removed_key = 'q'

        assert key in remove_query_param(q, removed_key)
        assert value in remove_query_param(q, removed_key)
        assert '%' not in remove_query_param(q, removed_key)

    def test_invalid_unicode(self):
        q = '/?from=login&page=2&%FF%FE%3C%73%63%72%69%70%74%3E%61%6C%65%72%74%28%33%31%33%29%3C%2F%73%63%72%69%70%74%3E=1'
        key = 'from'
        removed_key = 'page'

        assert key in remove_query_param(q, removed_key)
