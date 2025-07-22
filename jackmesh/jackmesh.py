import subprocess
import toml
import argparse
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
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
        return self.uuid == other.uuid

    def __hash__(self):
        return hash(self.uuid)

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

    def __hash__(self):
        return hash((self.output.name, self.input.name))

    def disconnect(self):
        status = jacklib.jack_status_t()
        result = jacklib.disconnect(self.client, self.output.name, self.input.name)
        if result != 0:
            error_msg = get_jack_status_error_string(status)
            raise Exception(f"Error disconnecting: {error_msg}")

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

        return self.ports

    def get_port_by_name(self, port_name):
        for port in self.get_jack_ports():
            if port.name == port_name:
                return port
        return None

    def get_ports_by_regex(self, port_regex):
        """Get all ports matching a name regex."""
        pattern = re.compile(port_regex)
        return [port for port in self.get_jack_ports() if pattern.match(port.name)]


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
        ports = self.get_jack_ports()
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
                    connection = PortConnection(self.client, output=source_port, input=dest_port)
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


def load(config_path, regex_matching=False, disconnect=False):
    """
    Loads JACK connections from a TOML configuration file.

    This function reads a specified TOML file to determine which JACK ports to connect or disconnect.
    It can handle both explicit port names and regular expressions for more flexible configurations.
    It also has an option to disconnect all existing connections before applying the new ones.

    Args:
        config_path (str): The path to the TOML configuration file.
        regex_matching (bool, optional): If True, allows the use of regular expressions for port names
                                         in the config file. Defaults to False.
        disconnect (bool, optional): If True, all existing JACK connections will be disconnected before
                                     the new connections from the config file are made. Defaults to False.
    """
    # Initialize the JackHandler to interact with the JACK server.
    jh = JackHandler()
    # Load the connection configuration from the specified TOML file.
    config = toml.load(config_path)
    # Retrieve a list of all currently active JACK connections.
    existing_connections = jh.get_jack_connections()

    # If the 'disconnect' flag is set, disconnect all existing connections.
    # This is useful for ensuring a clean state before applying a new configuration.
    if disconnect:
        def disconnect_all_and_print(connection):
            connection.disconnect()
            print(f"Disconnected {connection.output.name} from {connection.input.name}")

        with ThreadPoolExecutor() as executor:
            list(executor.map(disconnect_all_and_print, existing_connections))
        # After disconnecting, the list of existing connections is cleared.
        existing_connections = []

    # Prepare lists to hold the connection and disconnection operations defined in the config.
    connections_to_make = []
    disconnections_to_make = []

    # Iterate over the configuration file, which is structured by client, then by output port.
    for client, port_map in config.items():
        for output_key, inputs in port_map.items():
            # Check if the operation is a disconnection (prefixed with "disconnect:").
            is_disconnect = output_key.startswith("disconnect:")
            if is_disconnect:
                output_key = output_key[len("disconnect:"):]

            # Resolve the output port(s) from the configuration key.
            output_ports = []
            if "regex:" in output_key:
                if regex_matching:
                    # If regex is enabled, construct the regex pattern and find matching ports.
                    output_port_name_re = f"{client}:{output_key.replace('regex:', '')}"
                    output_ports.extend(jh.get_ports_by_regex(output_port_name_re))
                else:
                    raise RuntimeError(f"Port spec {output_key} requires regex matching to be enabled (-r flag)")
            else:
                # For non-regex, find the port by its exact name.
                output_port_name = f"{client}:{output_key}"
                output_port = jh.get_port_by_name(output_port_name)
                if output_port:
                    output_ports.append(output_port)

            # If no matching output ports are found, print a warning and skip.
            if not output_ports:
                print(f"Could not find any port for: {output_key}")
                continue

            # For each resolved output port, resolve the corresponding input port(s).
            for output_port in output_ports:
                for inp in inputs:
                    input_ports = []
                    if "regex:" in inp:
                        if regex_matching:
                            # Handle regex for input ports.
                            input_ports.extend(jh.get_ports_by_regex(inp.replace('regex:', '')))
                        else:
                            raise RuntimeError(f"Port spec {inp} requires regex matching to be enabled (-r flag)")
                    else:
                        # Handle exact names for input ports.
                        input_port = jh.get_port_by_name(inp)
                        if input_port:
                            input_ports.append(input_port)

                    # If no matching input ports are found, print a warning and skip.
                    if not input_ports:
                        print(f"Could not find any port for: {inp}")
                        continue

                    # Create PortConnection objects for each valid output-input pair.
                    for input_port in input_ports:
                        connection = PortConnection(output_port.client_ptr, output=output_port, input=input_port)
                        if is_disconnect:
                            disconnections_to_make.append(connection)
                        else:
                            connections_to_make.append(connection)

    # --- Execute Disconnections ---
    # A helper function to print and perform disconnection.
    def disconnect_and_print(connection):
        print(f"Disconnecting {connection.output.name} from {connection.input.name}...")
        connection.disconnect()

    # Filter the list of disconnections to only include those that actually exist.
    actual_disconnections = []
    for connection in disconnections_to_make:
        if connection in existing_connections:
            actual_disconnections.append(connection)
        else:
            print(f"Connection not found, cannot disconnect: {connection.output.name} to {connection.input.name}")

    # Perform the disconnections in parallel for efficiency.
    if actual_disconnections:
        with ThreadPoolExecutor() as executor:
            list(executor.map(disconnect_and_print, actual_disconnections))

        # Update the list of existing connections by removing the ones that were disconnected.
        existing_connections_set = set(existing_connections)
        actual_disconnections_set = set(actual_disconnections)
        existing_connections = list(existing_connections_set - actual_disconnections_set)

    # --- Execute Connections ---
    # A helper function to print and perform connection.
    def connect_and_print(connection):
        print(f"Connecting {connection.output.name} to {connection.input.name}...")
        connection.connect()

    # Filter the list of connections to only include those that don't already exist.
    actual_connections = []
    for connection in connections_to_make:
        if connection not in existing_connections:
            actual_connections.append(connection)
        else:
            print(f"Connection already established: {connection.output.name} to {connection.input.name}")

    # Perform the new connections in parallel.
    if actual_connections:
        with ThreadPoolExecutor() as executor:
            list(executor.map(connect_and_print, actual_connections))

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
    parser.add_argument('-r', '--regex', action="store_true", default=False,
                        help=f'Use regular expressions for client and port name matching')
    parser.add_argument('-x', '--disconnect', action="store_true", default=False,
                        help=f'Disconnect all existing connections before adding new')

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
        load(args.load, regex_matching=args.regex, disconnect=args.disconnect)

if __name__ == "__main__":
    main()
