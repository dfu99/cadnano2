# Cadnano2 DNA Origami Software (PyQt6 port)

## Overview
[Cadnano](http://cadnano.org/) is computer-aided design software for DNA origami nanostructures. The original citation is [here](https://academic.oup.com/nar/article/37/15/5001/2409858).

This version of Cadnano2 is being maintained by the [Douglas Lab](http://bionano.ucsf.edu/) to preserve the lattice-based design interface for research purposes. This is not a direct fork of [cadnano/cadnano2](https://github.com/cadnano/cadnano2) because that would result in a 200+ MB download when cloning. We have removed the [installer](https://github.com/cadnano/cadnano2/tree/master/installer) directory and git history, which makes this version less than 3 MB to download, or 11 MB uncompressed.

If you wish to use the newest version of Cadnano that supports Python scripting and non-lattice designs, see [cadnano2.5](https://github.com/cadnano/cadnano2.5/).

## License

This version of Cadnano2 is available under the MIT License.
GUI code that uses PyQt6 or PyQt3D is GPLv3 as [required](http://pyqt.sourceforge.net/Docs/PyQt6/introduction.html#license) by Riverbank Computing.
