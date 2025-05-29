# jackmesh

Manage your Jack audio server connections with ease using `jackmesh`, a lightweight Python utility that leverages plain TOML configuration files.

![License](https://github.com/omnitonal/jackmesh/blob/main/LICENSE)

## Features

- Dump current Jack connections in TOML format.
- Load Jack connections from TOML files. Default fallback to loading from `~/.jack_connections.toml` if no file specified.

## Installation

```bash
pip install jackmesh
```

## Usage

### Dump Current Jack Connections

To dump current jack connections to stdout in TOML format:

```bash
jackmesh -d
```

You can also redirect this output to a file:

```bash
jackmesh -d > my_connections.toml
```

### Load Jack Connections

Load jack connections using:

```bash
jackmesh -l path/to/your/file.toml
```

If no file is specified, `jackmesh` will by default look for `~/.jack_connections.toml`:

```bash
jackmesh -l
```

The assumption is that the TOML file provides the complete connection configuration and no other connections shall exist. Before applying the config file all existing connections will be removed.

## Configuration

`jackmesh` uses TOML format for its configuration files. An example of the configuration file:

```toml
[Pianoteq]
out_1 = [ "system:playback_FL",]
out_2 = [ "system:playback_FR",]

["Built-in Audio Pro"]
capture_AUX0 = [ "REAPER:in1",]
capture_AUX1 = [ "REAPER:in2",]

[REAPER]
out1 = [ "Built-in Audio Pro:playback_AUX0",]
out2 = [ "Built-in Audio Pro:playback_AUX1",]
```

## Future Improvements

* **Enhanced `JackHandler` Lifecycle:**
    * Implement context manager protocol (`__enter__`/`__exit__`) for automatic client cleanup.
    * Allow custom client names and manage client activation/deactivation explicitly.
* **Improved Port & Connection Management:**
    * Refine `PortConnection.disconnect` to use `jacklib.disconnect` for specific pairs.
    * Replace `jack_lsp` subprocess for listing connections with native `jacklib` calls (e.g., `jack_port_get_all_connections`).
    * Add method to force refresh of cached port list.
    * Provide methods in `JackHandler` for direct connection/disconnection of ports by name or object.
* **Error Handling & Logging:**
    * Introduce custom, specific exception classes (e.g., `JackPortNotFoundError`).
    * Integrate the `logging` module for more flexible diagnostics.
* **Usability & API Design:**
    * Support wildcard/regex matching for port names in operations.
    * Add comprehensive docstrings for all public APIs.
    * Ensure consistent return types for methods (e.g., `get_jack_ports` to return only `List[Port]`).
    * Remove unused internal methods like `_create_ports`.
* **Advanced Features:**
    * Implement support for JACK event callbacks (port registration, graph changes, server shutdown).
* **Code Quality:**
    * Ensure all strings passed to `jacklib` are properly encoded/decoded (UTF-8).
    * Complete and verify type hinting.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## See also

- [jackmesh: A Tool for Managing Jack Audio Server Connections](https://www.omnitonal.com/jackmesh-a-tool-for-managing-jack-audio-server-connections/)

## License

[GNU GPL v3](https://github.com/omnitonal/jackmesh/blob/main/LICENSE)
```
