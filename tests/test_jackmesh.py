import unittest
from unittest.mock import MagicMock, patch
from jackmesh.jackmesh import load, Port, PortConnection

class TestJackmesh(unittest.TestCase):

    @patch('jackmesh.jackmesh.toml.load')
    @patch('jackmesh.jackmesh.JackHandler')
    @patch('jackmesh.jackmesh.PortConnection.disconnect')
    @patch('jackmesh.jackmesh.PortConnection.connect')
    def test_disconnect_logic(self, mock_connect, mock_disconnect, MockJackHandler, mock_toml_load):
        # Mock config
        mock_toml_load.return_value = {
            "TestClient": {
                "disconnect:output1": ["input1"],
                "output2": ["input2"]
            }
        }

        # Mock JackHandler instance and its methods
        mock_handler_instance = MockJackHandler.return_value
        
        # Mock ports
        output_port1 = Port(MagicMock(), "TestClient:output1", "TestClient", MagicMock(), "output1", "audio", "uuid1", "output", [], 0, 0, 0)
        input_port1 = Port(MagicMock(), "input1", "SomeOtherClient", MagicMock(), "input1", "audio", "uuid2", "input", [], 0, 0, 0)
        output_port2 = Port(MagicMock(), "TestClient:output2", "TestClient", MagicMock(), "output2", "audio", "uuid3", "output", [], 0, 0, 0)
        input_port2 = Port(MagicMock(), "input2", "SomeOtherClient", MagicMock(), "input2", "audio", "uuid4", "input", [], 0, 0, 0)

        mock_handler_instance.get_port_by_name.side_effect = lambda name: {
            "TestClient:output1": output_port1,
            "input1": input_port1,
            "TestClient:output2": output_port2,
            "input2": input_port2
        }.get(name)

        # Mock existing connections
        existing_connection = PortConnection(MagicMock(), output=output_port1, input=input_port1)
        mock_handler_instance.get_jack_connections.return_value = [existing_connection]

        # Call the load function
        load("dummy_path.toml")

        # Assertions
        # Verify that disconnect is called for the specified connection
        mock_disconnect.assert_called_once()
        
        # Verify that connect is called for the other connection
        mock_connect.assert_called_once()

    @patch('jackmesh.jackmesh.toml.load')
    @patch('jackmesh.jackmesh.JackHandler')
    @patch('jackmesh.jackmesh.PortConnection.connect')
    def test_regex_logic(self, mock_connect, MockJackHandler, mock_toml_load):
        # Mock config
        mock_toml_load.return_value = {
            "TestClient": {
                "regex:output.*": ["regex:input.*"]
            }
        }

        # Mock JackHandler instance and its methods
        mock_handler_instance = MockJackHandler.return_value
        
        # Mock ports
        output_port1 = Port(MagicMock(), "TestClient:output1", "TestClient", MagicMock(), "output1", "audio", "uuid1", "output", [], 0, 0, 0)
        output_port2 = Port(MagicMock(), "TestClient:output2", "TestClient", MagicMock(), "output2", "audio", "uuid2", "output", [], 0, 0, 0)
        input_port1 = Port(MagicMock(), "SomeOtherClient:input1", "SomeOtherClient", MagicMock(), "input1", "audio", "uuid3", "input", [], 0, 0, 0)
        input_port2 = Port(MagicMock(), "SomeOtherClient:input2", "SomeOtherClient", MagicMock(), "input2", "audio", "uuid4", "input", [], 0, 0, 0)

        mock_handler_instance.get_ports_by_regex.side_effect = lambda regex: {
            "output.*": [output_port1, output_port2],
            "input.*": [input_port1, input_port2]
        }.get(regex, [])

        mock_handler_instance.get_jack_connections.return_value = []

        # Call the load function with regex matching enabled
        load("dummy_path.toml", regex_matching=True)

        # Assertions
        # Verify that connect is called for all combinations of matching ports
        self.assertEqual(mock_connect.call_count, 4)

if __name__ == '__main__':
    unittest.main()
