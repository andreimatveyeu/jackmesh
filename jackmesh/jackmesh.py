import subprocess
import toml
import argparse
import os

def get_jack_connections():
    """Fetch JACK connections using the jack_lsp command."""
    output = subprocess.check_output(["jack_lsp", "-c"], text=True).strip().split("\n")
    connections = {}

    i = 0
    while i < len(output):
        source = output[i].strip()
        if i + 1 < len(output) and not output[i+1].startswith("   "):  # Ensure the next line exists and it's a destination.
            i += 1
            continue

        dests = []
        i += 1
        while i < len(output) and output[i].startswith("   "):  # Loop over destinations.
            dests.append(output[i].strip())
            i += 1

        connections[source] = dests

    return connections


def find_port_by_substrings(port_list, substrings):
    for port in port_list:
        if all(substr in port for substr in substrings):
            return port.strip()
    return None

def disconnect_all_from_port(port):
    connections = subprocess.check_output(["jack_lsp", "-c"], text=True).strip().split("\n")
    for index, line in enumerate(connections):
        if port in line:
            connected_port = connections[index + 1].strip()

            # Skip if both are output ports (based on naming convention)
            if "playback" in port and "playback" in connected_port:
                continue
            elif "out" in port and "out" in connected_port:
                continue

            try:
                subprocess.run(["jack_disconnect", port, connected_port], check=True, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                # Check if error indicates already disconnected
                if "already disconnected" in e.stderr.decode('utf-8'):
                    continue
                else:
                    raise e


def load(config_path):
    # Load TOML configuration
    config = toml.load(config_path)

    # Get the list of available JACK ports
    ports = subprocess.check_output(["jack_lsp"], text=True).strip().split("\n")

    # Process each section in the TOML file
    for src, dest_patterns in config.items():
        for dest, substrings in dest_patterns.items():
            src_port = find_port_by_substrings(ports, [src])
            dest_port = find_port_by_substrings(ports, substrings)

            if src_port and dest_port:
                disconnect_all_from_port(dest_port)
                print(f"Connecting {src_port} to {dest_port}...")
                subprocess.run(["jack_connect", src_port, dest_port], check=True)
            else:
                print(f"Could not establish connection for {src} -> {dest}")

def dump():
    connections = get_jack_connections()
    formatted_connections = {}
    seen_connections = set()

    for source, dests in connections.items():
        client, port = source.split(":", 1)
        if client not in formatted_connections:
            formatted_connections[client] = {}

        # Only list the output if it has connections and avoid reverse duplicates
        if dests:
            for dest in dests:
                if (dest, source) not in seen_connections:
                    if port not in formatted_connections[client]:
                        formatted_connections[client][port] = []
                    formatted_connections[client][port].append(dest)
                    seen_connections.add((source, dest))

    # Filter out clients with no connections
    clients_to_remove = [client for client, ports in formatted_connections.items() if not ports]
    for client in clients_to_remove:
        del formatted_connections[client]

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
