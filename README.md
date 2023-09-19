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

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## See also

- [jackmesh: A Tool for Managing Jack Audio Server Connections](https://www.omnitonal.com/jackmesh-a-tool-for-managing-jack-audio-server-connections/)

## License

[GNU GPL v3](https://github.com/omnitonal/jackmesh/blob/main/LICENSE)
```
