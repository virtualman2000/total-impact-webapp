from totalimpactwebapp import db
from totalimpactwebapp import util
from totalimpactwebapp import json_sqlalchemy
from totalimpactwebapp.metric import Metric

class Snap(db.Model):

    last_collected_date = db.Column(db.DateTime())
    raw_value = db.Column(json_sqlalchemy.JSONAlchemy(db.Text))
    drilldown_url = db.Column(db.Text)
    number_times_collected = db.Column(db.Integer)
    first_collected_date = db.Column(db.DateTime())
    snap_id = db.Column(db.Text, primary_key=True)
    provider = db.Column(db.Text)
    interaction = db.Column(db.Text)

    # foreign keys
    tiid = db.Column(db.Text, db.ForeignKey("item.tiid"))



    def __init__(self, **kwargs):
        self.refset = None
        super(Snap, self).__init__(**kwargs)


    def set_refset(self, refset):
        self.refset = refset


    @property
    def raw_value_cleaned_for_export(self):
        PROVIDERS_WHO_DONT_ALLOW_EXPORT = ["scopus", "citeulike"]
        if self.provider in PROVIDERS_WHO_DONT_ALLOW_EXPORT:
            return "redacted"
        else:
            return self.raw_value


    def to_dict(self):
        return {
            "collected_date": self.last_collected_date,
            "value": self.raw_value,
            "drilldown_url": self.drilldown_url,
            "percentile": self.percentile
        }

    @property
    def can_diff(self):
        try:
            _ = int(self.raw_value)
            return True
        except (ValueError, TypeError):
            return False

    @property
    def display_count(self):
        try:
            return int(self.raw_value)
        except ValueError:
            # deal with F1000's troublesome "count" of "Yes."
            # currently ALL strings are transformed to 1.
            return 1
        except TypeError:
            return 0  # ignore lists and dicts


    @property
    def percentile(self):
        try:
            return self.percentile_full_dict["percentile"]
        except TypeError:
            return None

    @property
    def percentile_full_dict(self):
        return self.refset.get_percentile(
            self.provider,
            self.interaction,
            self.raw_value
        )

    @property
    def percentile_string(self):
        try:
            return util.ordinal(self.percentile)
        except TypeError:
            return None

    @property
    def is_highly(self):
        try:
            percentile_high_enough = self.percentile >= 75
        except TypeError:  # no percentiles listed
            percentile_high_enough = False

        raw_high_enough = self.display_count >= 3

        if percentile_high_enough and raw_high_enough:
            return True
        else:
            return False






