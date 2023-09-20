import subprocess
import toml
import argparse
import os
import sys
from typing import List, Literal
import jacklib
from jacklib.helpers import c_char_p_p_to_list, get_jack_status_error_string

import subprocess
from typing import List, Dict

import subprocess
from typing import List, Dict, Tuple
from typing import Optional


class Port:

    def __init__(self, port_ptr, name: str, client: str, client_ptr, port_name: str, port_type: str, uuid: str, direction: str,
                 aliases: List[str], in_latency: int, out_latency: int, total_latency: int):
        self.port_ptr = port_ptr
        self.name = name
        self.client = client
        self.client_ptr = client_ptr
        self.port_name = port_name
        self.port_type = port_type
        self.uuid = uuid
        self.direction = direction
        self.aliases = aliases
        self.in_latency = in_latency
        self.out_latency = out_latency
        self.total_latency = total_latency

    def __repr__(self) -> str:
        return f"Port(name='{self.name}', client='{self.client}', port_name='{self.port_name}', type='{self.port_type}', uuid='{self.uuid}', direction='{self.direction}', aliases={self.aliases}, in_latency={self.in_latency}, out_latency={self.out_latency}, total_latency={self.total_latency})"

    def __eq__(self, other):
        self.uuid == other.uuid

class PortConnection:

    def __init__(self, client, output: Optional['Port'] = None, input: Optional['Port'] = None):
        self.client = client
        if output and output.direction != 'output':
            raise ValueError(f"Expected an output port, but got {output.direction} port: {output.name}")
        if input and input.direction != 'input':
            raise ValueError(f"Expected an input port, but got {input.direction} port: {input.name}")

        self.output = output  # Output port
        self.input = input    # Input port

    def __repr__(self) -> str:
        return f"PortConnection(output={self.output}, input={self.input})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, PortConnection):
            return False
        return self.output.name == other.output.name and self.input.name == other.input.name

    def disconnect(self):
        # Disconnect output
        status = jacklib.jack_status_t()
        result = jacklib.port_disconnect(self.client, self.output.port_ptr)
        if result != 0:
            error_msg = get_jack_status_error_string(status)
            raise Exception(f"Error disconnecting output: {error_msg}")

        # Disconnect input
        status = jacklib.jack_status_t()
        result = jacklib.port_disconnect(self.client, self.input.port_ptr)
        if result != 0:
            error_msg = get_jack_status_error_string(status)
            raise Exception(f"Error disconnecting input: {error_msg}")

    def connect(self):
        status = jacklib.jack_status_t()
        result = jacklib.connect(self.client, self.output.name, self.input.name)

        # Handling any errors if they arise
        if result != 0:
            error_msg = get_jack_status_error_string(status)
            raise Exception(f"Error connecting: {error_msg}")


class JackHandler:

    def __init__(self):
        status = jacklib.jack_status_t()
        self.client = jacklib.client_open("PythonJackClient", jacklib.JackNoStartServer, status)
        err = get_jack_status_error_string(status)

        if status.value:
            if status.value & jacklib.JackNameNotUnique:
                print("Non-fatal JACK status: %s" % err, file=sys.stderr)
            elif status.value & jacklib.JackServerStarted:
                # Should not happen, since we use the JackNoStartServer option
                print("Unexpected JACK status: %s" % err, file=sys.stderr)
            else:
                raise Exception("Error connecting to JACK server: %s" % err)

        self.ports = None

    def get_jack_ports(self) -> List[Port]:
        if self.ports is not None:
            return self.ports

        port_names = c_char_p_p_to_list(jacklib.get_ports(self.client))
        self.ports = []

        for port_name in port_names:
            port_ptr = jacklib.port_by_name(self.client, port_name)
            uuid = jacklib.port_uuid(port_ptr)
            client, port_short_name = port_name.split(":", 1)

            port_type = jacklib.port_type(port_ptr)
            port_flags = jacklib.port_flags(port_ptr)
            direction = "input" if port_flags & jacklib.JackPortIsInput else "output"

            aliases = jacklib.port_get_aliases(port_ptr)[1:]


            in_range = jacklib.jack_latency_range_t()
            out_range = jacklib.jack_latency_range_t()

            jacklib.port_get_latency_range(port_ptr, jacklib.JackCaptureLatency, in_range)
            jacklib.port_get_latency_range(port_ptr, jacklib.JackPlaybackLatency, out_range)

            in_latency = in_range.min  # or in_range.max based on the range specifics
            out_latency = out_range.min  # or out_range.max based on the range specifics

            total_latency = jacklib.port_get_total_latency(self.client, port_ptr)

            port_instance = Port(port_ptr, port_name, client, self.client, port_short_name, port_type, uuid, direction, aliases, in_latency, out_latency, total_latency)
            self.ports.append(port_instance)

        return self.client, self.ports

    def get_port_by_name(self, port_name):
        for port in self.get_jack_ports():
            if port.name == port_name:
                return port
        return None

    def _create_ports(self, properties_output: List[str], type_dict: Dict[str, str], uuid_dict: Dict[str, str],
                    alias_dict: Dict[str, List[str]], latency_dict: Dict[str, Tuple[int, int]],
                    total_latency_dict: Dict[str, int]) -> List[Port]:
        ports = []
        for i in range(0, len(properties_output), 2):
            port_full_name = properties_output[i].strip()
            client, port_name = port_full_name.split(":", 1)

            # Parse the properties to get the direction (input/output)
            properties = properties_output[i + 1].strip().replace("properties:", "").split(',')
            properties = [ p.strip() for p in properties ]
            direction = "input" if "input" in properties else "output"

            port_type = type_dict.get(port_full_name, "unknown")
            if "raw midi" in port_type:
                port_type = "midi"

            uuid = uuid_dict.get(port_full_name, "")
            aliases = alias_dict.get(port_full_name, [])
            in_latency, out_latency = latency_dict.get(port_full_name, (0, 0))
            total_latency = total_latency_dict.get(port_full_name, 0)

            port = Port(port_full_name, client, port_name, port_type, uuid, direction, aliases, in_latency, out_latency, total_latency)
            ports.append(port)

        return ports

    def get_jack_connections(self) -> List[PortConnection]:
        """Fetch JACK connections using the jack_lsp command and return them as a list of PortConnection instances."""
        # Retrieve all Port instances
        client, ports = self.get_jack_ports()
        port_map = {port.name: port for port in ports}  # Create a dict for easy lookup

        # Read the connections
        output = subprocess.check_output(["jack_lsp", "-c"], text=True).strip().split("\n")

        # Create PortConnection instances
        connections = []
        i = 0
        while i < len(output):
            source_name = output[i].strip()
            source_port = port_map.get(source_name)

            # Ensure the next line exists and it's a destination.
            if i + 1 < len(output) and not output[i+1].startswith("   "):
                i += 1
                continue

            # Loop over destinations
            i += 1
            while i < len(output) and output[i].startswith("   "):
                dest_name = output[i].strip()
                dest_port = port_map.get(dest_name)

                # Check if the source is an output and the destination is an input
                if source_port and dest_port and source_port.direction == "output" and dest_port.direction == "input":
                    connection = PortConnection(client, output=source_port, input=dest_port)
                    # Ensure we're not adding duplicate connections
                    if connection not in connections:
                        connections.append(connection)
                i += 1

        return connections

    def get_client_names(self):
        """Get a sorted list of unique client names from the ports."""
        # Fetch all ports
        ports = self.get_jack_ports()

        # Extract the client names from the ports
        client_names = set(port.client for port in ports)

        return sorted(client_names)

    def get_ports_by_client_name(self, client_name: str) -> List[Port]:
        """Return a list of Port objects associated with the given client name."""
        ports = self.get_jack_ports()
        return [port for port in ports if port.client == client_name]


def load(config_path):
    jh = JackHandler()

    # Load TOML configuration
    config = toml.load(config_path)

    # Disconnect all existing connections
    existing_connections = jh.get_jack_connections()
    for connection in existing_connections:
        connection.disconnect()
        print(f"Disconnected {connection.output.name} from {connection.input.name}")

    # Process each section in the TOML file to establish new connections
    for client, port_map in config.items():
        for output, inputs in port_map.items():
            output_port_name = f"{client}:{output}"
            output_port = jh.get_port_by_name(output_port_name)
            if output_port is None:
                print(f"Could not find port: {output_port_name}")
                continue
            for inp in inputs:
                input_port = jh.get_port_by_name(inp)
                if input_port is None:
                    print(f"Could not find port: {inp}")
                    continue
                connection = PortConnection(output_port.client_ptr, output=output_port, input=input_port)
                print(f"Connecting {output_port.name} to {input_port.name}...")
                connection.connect()

def dump():
    jh = JackHandler()

    # Get all connections
    connections = jh.get_jack_connections()

    # Build a mapping from source port to list of destination ports
    connections_map = {}
    for connection in connections:
        if connection.output.name not in connections_map:
            connections_map[connection.output.name] = []
        connections_map[connection.output.name].append(connection.input.name)

    # Get a list of all unique client names
    clients = jh.get_client_names()

    # Create a dictionary in the required format
    formatted_connections = {}
    for client in clients:
        ports = jh.get_ports_by_client_name(client)
        for port in ports:
            source = port.name
            if source in connections_map:
                _, port_name = source.split(":", 1)
                if client not in formatted_connections:
                    formatted_connections[client] = {}
                formatted_connections[client][port_name] = connections_map[source]

    # Convert dictionary to TOML and print
    toml_str = toml.dumps(formatted_connections)
    print(toml_str)

def main():
    # Create the argument parser object.
    parser = argparse.ArgumentParser(description="jackmesh: A utility to load or dump Jack audio server connections using a TOML configuration.")

    # Add arguments for loading and dumping configurations.
    default_config_file = os.path.expanduser("~/.jack_connections.toml")
    parser.add_argument('-l', '--load',
                        nargs='?',  # This allows the argument to be optional
                        const=os.path.expanduser(default_config_file),  # This will be the default if '-l' is provided without a value
                        help=f'Load connections from a TOML configuration file. Defaults to {default_config_file} if no path is provided.')

    parser.add_argument('-d', '--dump', action="store_true",
                        help='Dump the current connections into a TOML configuration file. Provide the path to save the file.')

    # Parse the provided arguments.
    args = parser.parse_args()

    # Check if neither argument is provided.
    if not (args.load or args.dump):
        parser.error("You must provide either '-l/--load' or '-d/--dump' argument.")
    # Check if both arguments are provided.
    elif args.load and args.dump:
        parser.error("You can only provide either '-l/--load' or '-d/--dump' at a time, not both.")

    if args.dump:
        dump()
    elif args.load:
        load(args.load)

if __name__ == "__main__":
    main()
