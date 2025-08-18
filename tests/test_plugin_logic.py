import unittest
import sys
import os
from unittest.mock import MagicMock, patch

from tests.mock_utils import setup_qgis_mocks
setup_qgis_mocks()

# Add the parent directory to the Python path to allow sibling imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from reneW.reneW import ReneW
from reneW.calculation_logic import MaterialParams
from qgis.core import QgsPointXY, QgsGeometry

class TestReneWPluginLogic(unittest.TestCase):
    """Test suite for the main plugin logic in the ReneW class."""

    def setUp(self):
        """Set up a mock plugin instance for each test."""
        self.iface = MagicMock()
        self.plugin = ReneW(self.iface)
        self.plugin.dlg = MagicMock()

    @patch('reneW.reneW.QgsVectorLayer')
    @patch('reneW.reneW.material_lookup')
    def test_run_temporal_analysis_creates_features(self, mock_material_lookup, mock_qgs_vector_layer):
        """Test that the temporal analysis creates the correct number of features."""
        # --- Setup Mocks ---
        # Mock dialog settings for a 20-year analysis with a 5-year step
        self.plugin.dlg.useTemporalAnalysis.return_value = True
        self.plugin.dlg.useHotspotAnalysis.return_value = False  # Disable for this test
        self.plugin.dlg.temporalStartYear.return_value = 2025
        self.plugin.dlg.temporalEndYear.return_value = 2045
        self.plugin.dlg.temporalStep.return_value = 5  # This means 5 steps: 2025, 30, 35, 40, 45

        # Mock the input layer and its single feature
        mock_layer = MagicMock()
        mock_feature = MagicMock()
        mock_layer.featureCount.return_value = 1
        mock_layer.getFeatures.return_value = [mock_feature]
        # Make indexFromName return the correct index for each field
        def index_side_effect(name):
            return {'mat': 0, 'year': 1, 'reno_year_field': 2, 'reno_method_field': 3}[name]
        mock_layer.fields.return_value.indexFromName.side_effect = index_side_effect

        # Mock the analysis config to return our mock layer
        self.plugin.dlg.get_analysis_configs.return_value = [{
            'type': 'water',
            'layer': mock_layer,
            'material_field': 'mat',
            'year_field': 'year'
        }]

        # Mock the feature's attributes
        mock_feature.attributes.return_value = ['pvc', 2000] # mat, year
        mock_feature.geometry.return_value = MagicMock()
        mock_feature.id.return_value = 1

        # Mock the parameter lookup to return some dummy params
        mock_material_lookup.find_material_key.return_value = ('pvc', MaterialParams(mu=100, sigma=20))

        # --- Action ---
        self.plugin._run_temporal_analysis(params_data={})

        # --- Assertions ---
        # Check that a new memory layer was created
        mock_qgs_vector_layer.assert_called_with(unittest.mock.ANY, "Temporal Renewal Need", "memory")

        # Get the mock for the new layer's data provider
        mock_provider = mock_qgs_vector_layer.return_value.dataProvider.return_value

        # We have 1 feature, and 5 time steps (2025, 2030, 2035, 2040, 2045)
        # So, addFeature should have been called 5 times.
        self.assertEqual(mock_provider.addFeature.call_count, 5)

        # Check the attributes of the first feature created
        first_feature_mock = mock_provider.addFeature.call_args_list[0][0][0]
        first_feature_attrs = first_feature_mock.setAttributes.call_args[0][0]
        self.assertEqual(first_feature_attrs[2], 2025) # year attribute

        # Check the attributes of the last feature created
        last_feature_mock = mock_provider.addFeature.call_args_list[-1][0][0]
        last_feature_attrs = last_feature_mock.setAttributes.call_args[0][0]
        self.assertEqual(last_feature_attrs[2], 2045) # year attribute

    @patch('reneW.reneW.datetime')
    @patch('reneW.reneW.QgsSpatialIndex')
    @patch('reneW.reneW.QgsFeatureRequest')
    def test_infer_year_from_properties_logic(self, mock_qgs_feature_request, mock_qgs_spatial_index, mock_datetime):
        """Test the core logic of _infer_year_from_properties directly."""
        # --- Mocks & Setup ---
        mock_datetime.now.return_value.year = 2024

        # 1. Mock Pipe Feature
        mock_pipe_feature = MagicMock()
        mock_geom = MagicMock()
        mock_geom.isEmpty.return_value = False
        mock_geom.length.return_value = 100.0
        mock_point_geom = MagicMock()
        mock_point_geom.asPoint.return_value = QgsPointXY(10, 10)
        mock_point_geom.isEmpty.return_value = False
        mock_geom.interpolate.return_value = mock_point_geom
        mock_pipe_feature.geometry.return_value = mock_geom

        # 2. Mock Property Layer
        mock_prop_layer = MagicMock()
        mock_prop_features = []
        for i, year in enumerate([1980, 1995, 1982, 2050, None]): # Include invalid year and None
            feat = MagicMock()
            feat.id.return_value = i
            # This is key: the attribute call must be mocked correctly
            feat.attribute.return_value = year
            prop_geom = MagicMock()
            prop_geom.isEmpty.return_value = False
            feat.geometry.return_value = prop_geom
            mock_prop_features.append(feat)

        # When getFeatures is called on the prop layer, return our list
        mock_prop_layer.getFeatures.return_value = mock_prop_features
        mock_prop_layer.fields.return_value.indexFromName.return_value = 1 # 'prop_year_idx'

        # 3. Mock Spatial Index to return FIDs of all our mock features
        mock_index_instance = mock_qgs_spatial_index.return_value
        mock_index_instance.nearestNeighbor.return_value = [0, 1, 2, 3, 4]

        # --- Action ---
        inferred_year = self.plugin._infer_year_from_properties(
            mock_pipe_feature, mock_prop_layer, 'prop_year', 5
        )

        # --- Assertions ---
        # The method should find neighbours for the sample point
        mock_index_instance.nearestNeighbor.assert_called()

        # It should request the features for the found FIDs
        mock_qgs_feature_request.return_value.setFilterFids.assert_called_with([0, 1, 2, 3, 4])
        mock_prop_layer.getFeatures.assert_called()

        # The valid years are [1980, 1995, 1982]. 2050 is in the future, None is skipped.
        # The median of [1980, 1982, 1995] is 1982.
        self.assertEqual(inferred_year, 1982)


if __name__ == '__main__':
    unittest.main()
