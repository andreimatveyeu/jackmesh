import subprocess
import toml
import argparse
import os
from typing import List, Literal

import subprocess
from typing import List, Dict

import subprocess
from typing import List, Dict, Tuple
from typing import Optional


class Port:

    def __init__(self, name: str, client: str, port_name: str, port_type: str, uuid: str, direction: str,
                 aliases: List[str], in_latency: int, out_latency: int, total_latency: int):
        self.name = name
        self.client = client
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
    def __init__(self, output: Optional['Port'] = None, input: Optional['Port'] = None):
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
        try:
            subprocess.run(["jack_disconnect", self.output.name, self.input.name], check=True, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            # Check if error indicates already disconnected
            if "already disconnected" not in e.stderr.decode('utf-8'):
                raise e

    def connect(self):
        """Connects the output and input ports of this connection using the jack_connect command."""
        subprocess.run(["jack_connect", self.output.name, self.input.name], check=True)


class JackHandler:
    def __init__(self):
        pass

    def get_jack_ports(self) -> List[Port]:
        properties_output = self._run_jack_lsp('-p')
        type_output = self._run_jack_lsp('-t')
        uuid_output = self._run_jack_lsp('-U')
        alias_output = self._run_jack_lsp('-A')
        latency_output = self._run_jack_lsp('-l')
        total_latency_output = self._run_jack_lsp('-L')

        type_dict = self._parse_type(type_output)
        uuid_dict = self._parse_uuid(uuid_output)
        alias_dict = self._parse_aliases(alias_output)
        latency_dict = self._parse_latency(latency_output)
        total_latency_dict = self._parse_total_latency(total_latency_output)

        return self._create_ports(properties_output, type_dict, uuid_dict, alias_dict, latency_dict, total_latency_dict)

    def find_port_by_substrings(self, substrings):
        """Finds a port where its name contains all given substrings."""
        ports = self.get_jack_ports()

        for port in ports:
            if all(substr in port.name for substr in substrings):
                return port
        return None

    def _run_jack_lsp(self, option: str) -> List[str]:
        return subprocess.run(['jack_lsp', option], capture_output=True, text=True).stdout.splitlines()

    def _parse_type(self, output: List[str]) -> Dict[str, str]:
        return {output[i]: output[i + 1].strip() for i in range(0, len(output), 2)}

    def _parse_uuid(self, output: List[str]) -> Dict[str, str]:
        return {output[i]: output[i + 1].split(":")[1].strip() for i in range(0, len(output), 2)}

    def _parse_aliases(self, output: List[str]) -> Dict[str, List[str]]:
        alias_dict = {}
        i = 0
        while i < len(output):
            key = output[i]
            aliases = []
            i += 1
            while i < len(output) and output[i].startswith("   "):  # Check for indentation
                aliases.append(output[i].strip())
                i += 1
            alias_dict[key] = aliases
        return alias_dict

    def _parse_latency(self, output: List[str]) -> Dict[str, Tuple[int, int]]:
        latency_dict = {}
        for i in range(0, len(output), 3):
            out_latency = int(output[i + 1].split("[")[1].split()[0])
            in_latency = int(output[i + 2].split("[")[1].split()[0])
            latency_dict[output[i]] = (in_latency, out_latency)
        return latency_dict

    def _parse_total_latency(self, output: List[str]) -> Dict[str, int]:
        return {output[i]: int(output[i + 1].split("=")[1].split()[0]) for i in range(0, len(output), 2)}

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
                    connection = PortConnection(output=source_port, input=dest_port)
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
        for output, input_substrings in port_map.items():
            output_port = jh.find_port_by_substrings(substrings=[f"{client}:{output}"])
            input_port = jh.find_port_by_substrings(substrings=input_substrings)

            if output_port and input_port:
                connection = PortConnection(output=output_port, input=input_port)
                print(f"Connecting {output_port.name} to {input_port.name}...")
                connection.connect()
            else:
                print(f"Could not establish connection for {client} -> {output}")


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
