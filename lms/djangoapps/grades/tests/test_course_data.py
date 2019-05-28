"""
Tests for CourseData utility class.
"""
from __future__ import absolute_import

import six
from mock import patch

from lms.djangoapps.course_blocks.api import get_course_blocks
from openedx.core.djangoapps.content.block_structure.api import get_course_in_cache
from student.tests.factories import UserFactory
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ..course_data import CourseData


class CourseDataTest(ModuleStoreTestCase):
    """
    Simple tests to ensure CourseData works as advertised.
    """

    def setUp(self):
        super(CourseDataTest, self).setUp()
        with self.store.default_store(ModuleStoreEnum.Type.split):
            self.course = CourseFactory.create()
            # need to re-retrieve the course since the version on the original course isn't accurate.
            self.course = self.store.get_course(self.course.id)
        self.user = UserFactory.create()
        self.collected_structure = get_course_in_cache(self.course.id)
        self.one_true_structure = get_course_blocks(
            self.user, self.course.location, collected_block_structure=self.collected_structure,
        )
        self.expected_results = {
            'course': self.course,
            'collected_block_structure': self.collected_structure,
            'structure': self.one_true_structure,
            'course_key': self.course.id,
            'location': self.course.location,
        }

    @patch('lms.djangoapps.grades.course_data.get_course_blocks')
    def test_fill_course_data(self, mock_get_blocks):
        """
        Tests to ensure that course data is fully filled with just a single input.
        """
        mock_get_blocks.return_value = self.one_true_structure
        for kwarg in self.expected_results:  # We iterate instead of ddt due to dependence on 'self'
            if kwarg == 'location':
                continue  # This property is purely output; it's never able to be used as input
            kwargs = {kwarg: self.expected_results[kwarg]}
            course_data = CourseData(self.user, **kwargs)
            for arg in self.expected_results:
                # No point validating the data we used as input, and c_b_s is input-only
                if arg != kwarg and arg != "collected_block_structure":
                    expected = self.expected_results[arg]
                    actual = getattr(course_data, arg)
                    self.assertEqual(expected, actual)

    def test_properties(self):
        expected_edited_on = getattr(
            self.one_true_structure[self.one_true_structure.root_block_usage_key],
            'subtree_edited_on',
        )

        for kwargs in [
            dict(course=self.course),
            dict(collected_block_structure=self.one_true_structure),
            dict(structure=self.one_true_structure),
            dict(course_key=self.course.id),
        ]:
            course_data = CourseData(self.user, **kwargs)
            self.assertEquals(course_data.course_key, self.course.id)
            self.assertEquals(course_data.location, self.course.location)
            self.assertEquals(course_data.structure.root_block_usage_key, self.one_true_structure.root_block_usage_key)
            self.assertEquals(course_data.course.id, self.course.id)
            self.assertEquals(course_data.version, self.course.course_version)
            self.assertEquals(course_data.edited_on, expected_edited_on)
            self.assertIn(u'Course: course_key', six.text_type(course_data))
            self.assertIn(u'Course: course_key', course_data.full_string())

    def test_no_data(self):
        with self.assertRaises(ValueError):
            _ = CourseData(self.user)

    @patch.dict('django.conf.settings.FEATURES', {'DISABLE_START_DATES': False})
    def test_full_string(self):
        empty_structure = get_course_blocks(self.user, self.course.location)
        self.assertFalse(empty_structure)

        # full_string retrieves value from collected_structure when structure is empty.
        course_data = CourseData(
            self.user, structure=empty_structure, collected_block_structure=self.collected_structure,
        )
        self.assertIn(u'Course: course_key: {}, version:'.format(self.course.id), course_data.full_string())

        # full_string returns minimal value when structures aren't readily available.
        course_data = CourseData(self.user, course_key=self.course.id)
        self.assertIn(u'empty course structure', course_data.full_string())
