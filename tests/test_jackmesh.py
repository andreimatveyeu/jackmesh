import os
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch
from jackmesh.jackmesh import load, Port, PortConnection, _load_config_file, _merge_configs

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
            "TestClient:output.*": [output_port1, output_port2],
            "input.*": [input_port1, input_port2]
        }.get(regex, [])

        mock_handler_instance.get_jack_connections.return_value = []

        # Call the load function with regex matching enabled
        load("dummy_path.toml", regex_matching=True)

        # Assertions
        # Verify that connect is called for all combinations of matching ports
        self.assertEqual(mock_connect.call_count, 4)

class TestIncludes(unittest.TestCase):

    def _write(self, dirpath, name, body):
        path = os.path.join(dirpath, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(textwrap.dedent(body))
        return path

    def test_merge_concats_and_dedupes_lists(self):
        base = {"Client": {"out": ["a", "b"]}}
        _merge_configs(base, {"Client": {"out": ["b", "c"]}})
        self.assertEqual(base, {"Client": {"out": ["a", "b", "c"]}})

    def test_merge_preserves_disjoint_keys(self):
        base = {"Client": {"out1": ["a"]}}
        _merge_configs(base, {"Client": {"out2": ["b"]}, "Other": {"x": ["y"]}})
        self.assertEqual(base, {
            "Client": {"out1": ["a"], "out2": ["b"]},
            "Other": {"x": ["y"]},
        })

    def test_include_resolves_relative_paths_and_merges(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "midi.toml", """
                [Pianoteq]
                out_1 = ["system:playback_FL"]
            """)
            self._write(tmp, "sub/extra.toml", """
                [Pianoteq]
                out_1 = ["system:playback_FR"]
                out_2 = ["other:in"]
            """)
            root = self._write(tmp, "root.toml", """
                include = ["midi.toml", "sub/extra.toml"]

                [REAPER]
                out1 = ["system:playback_FL"]
            """)

            cfg = _load_config_file(root)
            self.assertEqual(cfg, {
                "Pianoteq": {
                    "out_1": ["system:playback_FL", "system:playback_FR"],
                    "out_2": ["other:in"],
                },
                "REAPER": {"out1": ["system:playback_FL"]},
            })

    def test_disconnect_keys_merge_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.toml", """
                [Firefox]
                "disconnect:output_FL" = ["ardour:Firefox/audio_in 1"]
            """)
            root = self._write(tmp, "root.toml", """
                include = ["a.toml"]

                [Firefox]
                "disconnect:output_FL" = ["ardour:Firefox/audio_in 2"]
            """)
            cfg = _load_config_file(root)
            self.assertEqual(cfg["Firefox"]["disconnect:output_FL"], [
                "ardour:Firefox/audio_in 1",
                "ardour:Firefox/audio_in 2",
            ])

    def test_circular_include_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.toml")
            b = os.path.join(tmp, "b.toml")
            with open(a, "w") as f:
                f.write('include = ["b.toml"]\n')
            with open(b, "w") as f:
                f.write('include = ["a.toml"]\n')
            with self.assertRaises(RuntimeError):
                _load_config_file(a)


if __name__ == '__main__':
    unittest.main()
