from django.conf import settings
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from django.utils.translation import gettext as _


class BaseLock:
    """
    Holds information about a lock on an object.

    Returned by LockableMixin.get_lock() (or Page.get_lock()).
    """

    def __init__(self, object):
        from wagtail.models import Page

        self.object = object
        self.is_page = isinstance(object, Page)

    def for_user(self, user):
        """
        Returns True if the lock applies to the given user.
        """
        return NotImplemented

    def get_message(self, user):
        """
        Returns a message to display to the given user describing the lock.
        """
        return None


class BasicLock(BaseLock):
    """
    A lock that is enabled when the "locked" attribute of a page is True.

    The object may be editable by a user depending on whether the locked_by field is set
    and if WAGTAILADMIN_GLOBAL_PAGE_EDIT_LOCK is not set to True.
    """

    def for_user(self, user):
        if getattr(settings, "WAGTAILADMIN_GLOBAL_PAGE_EDIT_LOCK", False):
            return True
        else:
            return user.pk != self.object.locked_by_id

    def get_message(self, user):
        if self.object.locked_by_id == user.pk:
            if self.object.locked_at:
                return format_html(
                    # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                    _(
                        "<b>Page '{page_title}' was locked</b> by <b>you</b> on <b>{datetime}</b>."
                    ),
                    page_title=self.object.get_admin_display_title(),
                    datetime=self.object.locked_at.strftime("%d %b %Y %H:%M"),
                )

            else:
                return format_html(
                    # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                    _("<b>Page '{page_title}' is locked</b> by <b>you</b>."),
                    page_title=self.object.get_admin_display_title(),
                )
        else:
            if self.object.locked_by and self.object.locked_at:
                return format_html(
                    # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                    _(
                        "<b>Page '{page_title}' was locked</b> by <b>{user}</b> on <b>{datetime}</b>."
                    ),
                    page_title=self.object.get_admin_display_title(),
                    user=str(self.object.locked_by),
                    datetime=self.object.locked_at.strftime("%d %b %Y %H:%M"),
                )
            else:
                # Page was probably locked with an old version of Wagtail, or a script
                return format_html(
                    # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                    _("<b>Page '{page_title}' is locked</b>."),
                    page_title=self.object.get_admin_display_title(),
                )


class WorkflowLock(BaseLock):
    """
    A lock that requires the user to pass the Task.page_locked_for_user test on the given workflow task.

    Can be applied to pages only.
    """

    def __init__(self, object, task):
        super().__init__(object)
        self.task = task

    def for_user(self, user):
        return self.task.page_locked_for_user(self.object, user)

    def get_message(self, user):
        if self.for_user(user):
            if len(self.object.current_workflow_state.all_tasks_with_status()) == 1:
                # If only one task in workflow, show simple message
                workflow_info = _("This page is currently awaiting moderation.")
            else:
                workflow_info = format_html(
                    # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                    _(
                        "This page is awaiting <b>'{task_name}'</b> in the <b>'{workflow_name}'</b> workflow."
                    ),
                    task_name=self.task.name,
                    workflow_name=self.object.current_workflow_state.workflow.name,
                )

            return mark_safe(
                workflow_info
                + " "
                + _("Only reviewers for this task can edit the page.")
            )


class ScheduledForPublishLock(BaseLock):
    """
    A lock that occurs when something is scheduled to be published.

    This prevents it becoming difficult for users to see which version is going to be published.
    Nobody can edit something that's scheduled for publish.
    """

    def for_user(self, user):
        return True

    def get_message(self, user):
        scheduled_revision = self.object.scheduled_revision

        if self.is_page:
            return format_html(
                # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                _(
                    "Page '{page_title}' is locked and has been scheduled to go live at {datetime}"
                ),
                page_title=self.object.get_admin_display_title(),
                datetime=scheduled_revision.approved_go_live_at.strftime(
                    "%d %b %Y %H:%M"
                ),
            )
        else:
            message = format_html(
                # nosemgrep: translation-no-new-style-formatting (new-style only w/ format_html)
                _(
                    "{model_name} '{title}' is locked and has been scheduled to go live at {datetime}"
                ),
                model_name=self.object._meta.verbose_name,
                title=scheduled_revision.object_str,
                datetime=scheduled_revision.approved_go_live_at.strftime(
                    "%d %b %Y %H:%M"
                ),
            )
            return mark_safe(capfirst(message))
