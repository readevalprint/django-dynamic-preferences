import collections

from .settings import preferences_settings
from .exceptions import CachedValueNotFound, DoesNotExist


class PreferencesManager(collections.Mapping):

    """Handle retrieving / caching of preferences"""

    def __init__(self, model, registry, **kwargs):

        self.model = model

        self.registry = registry
        self.queryset = self.model.objects.all()
        self.instance = kwargs.get('instance')
        if self.instance:
            self.queryset = self.queryset.filter(instance=self.instance)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        section, name = self.parse_lookup(key)
        self.update_db_pref(section=section, name=name, value=value)

    def __repr__(self):
        return repr(self.all())

    def __iter__(self):
        return self.all().__iter__()

    def __len__(self):
        return len(self.all())

    def by_name(self):
        """Return a dictionary with preferences identifiers and values, but without the section name in the identifier"""
        return {key.split(preferences_settings.SECTION_KEY_SEPARATOR)[-1]: value for key, value in self.all().items()}

    def get_by_name(self, name):
        return self.get(self.registry.get_by_name(name).identifier())

    def pref_obj(self, section, name):
        return self.registry.get(section=section, name=name)

    def parse_lookup(self, lookup):
        try:
            section, name = lookup.split(
                preferences_settings.SECTION_KEY_SEPARATOR)
        except ValueError:
            name = lookup
            section = None
        return section, name

    def get(self, key):
        """Return the value of a single preference using a dotted path key
        :arg no_cache: if true, the cache is bypassed
        """
        section, name = self.parse_lookup(key)
        return self.get_db_pref(section=section, name=name).value

    def get_db_pref(self, section, name):
        try:
            pref = self.queryset.get(section=section, name=name)

        except self.model.DoesNotExist:
            pref_obj = self.pref_obj(section=section, name=name)
            pref = self.create_db_pref(
                section=section, name=name, value=pref_obj.default)

        return pref

    def update_db_pref(self, section, name, value):
        try:
            db_pref = self.queryset.get(section=section, name=name)
            db_pref.value = value
            db_pref.save()
        except self.model.DoesNotExist:
            return self.create_db_pref(section, name, value)

        return db_pref

    def create_db_pref(self, section, name, value):
        kwargs = {
            'section': section,
            'name': name,
        }
        if self.instance:
            kwargs['instance'] = self.instance
            db_pref = self.model(
                section=section, name=name, instance=self.instance)
        else:
            db_pref = self.model(section=section, name=name)

        db_pref, created = self.model.objects.get_or_create(**kwargs)
        db_pref.value = value
        db_pref.save()

        return db_pref

    def all(self):
        """Return a dictionary containing all preferences by section
        Loaded from cache or from db in case of cold cache
        """
        return self.load_from_db()


    def load_from_db(self):
        """Return a dictionary of preferences by section directly from DB"""
        a = {}
        db_prefs = {p.preference.identifier(): p for p in self.queryset}
        for preference in self.registry.preferences():
            try:
                db_pref = db_prefs[preference.identifier()]
            except KeyError:
                db_pref = self.create_db_pref(
                    section=preference.section.name, name=preference.name, value=preference.default)

            a[preference.identifier()] = db_pref
        return a
