# cortex-annotate

A toolkit for annotating contours and boundaries on the cortical surface.

## About

### Author
Noah C. Benson &lt;[nben@uw.edu](mailto:nben@uw.edu)&gt;

### License
[MIT](https://opensource.org/license/mit/)

### About
The `cortex-annotate` repository is designed to be an easy-to-use toolkit for
MRI researchers who study the human brain to annotate boundaries and contours on
the cortical surface. Because any two research projects that require boundaries
or annotations are unlikely to be substantially similar, the toolkit is highly
flexible and must be customized using a standard file that combines yaml and
Python.

The `cortex-annotate` tool has been designed to make publicly storing datasets
of contours straightforward. This design is based on the workflow developed for
the [`hcp-annot-vc`](https://github.com/noahbenson/hcp-annot-vc) repository. A
typical workflow for the use of `cortex-annotate` to annotate a single brain
area as part of a project proceeds as follows:
1. The project lead forks the `cortex-annotate` repository and edits the forked
   repository to document relevant metadata (name, description, etc.). This
   forked repository becomes the **main repository** for the specific annotation
   project.
   * As part of the customization, the project lead will edit the
     `config/config.yaml` file, which contains all the configuration details for
     dataset that is to be annotated by the tool.
   * In particular, this configuration file will include all the relevant Python
     code for creating 2D projections or flatmaps of the brain on which the
     contours are drawn; see the README in the `config` directory of this
     repository for more information.
2. Once the forked repository has been customized, individual GitHub users will
   fork the **main repository** into their own GitHub accounts.
3. Each individual user then clones their fork of the **main repository** on
   their local computers and runs the `docker-compose up` command. This starts a
   docker container that runs a Jupyter notebook containing the annotation tool
   itself. The tool reads from the `config/config.yaml` file to determine how to
   present the relevant relevant annotation images.
4. Individual users interact with the annotation tool in the Jupyter notebook
   using the mouse and a few keys to click on contours points. These contours
   are saved into JSON files in the repository directory; the file names are
   specified in the `config/config.yaml` file, and the directory is determined
   in part by the users's GitHub username.
5. When a user has finished (or partially finished) annotating the dataset, they
   exit the tool and can submit their contours to their GitHub repository using
   `git commit` and `git push`. When they are finished with their contours, they
   can open a pull request to the `data` branch of the **main repository** in
   order to submit their annotations back to the project lead. Because the
   annotations are placed in the `data` branch, the `main` branch remains clean
   and can be quickly forked by new annotators.
