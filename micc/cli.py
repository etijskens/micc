# -*- coding: utf-8 -*-

"""
Application micc
"""

import os,sys
from types import SimpleNamespace
from pathlib import Path
from operator import xor

import click

import micc.commands as cmds
import micc.utils
import micc.logging_tools
import micc.expand

__template_help  =  "Ordered list of Cookiecutter templates, or a single Cookiecutter template."

__micc_file_help = ("The path to the *micc-file* with the parameter values used in the cookiecutter"
                    "templates. When a new project is created, "
                    "in the cookiecutter templates (default = ``micc.json``). "
                    "*Micc* does not use the standard ``cookiecutter.json`` file to provide the "
                    "template parameters, but uses a *micc-file*, usually named ``micc.json``, to "
                    "generate a ``cookiecutter.json`` file. Unlike the ``cookiecutter.json`` file, "
                    "the ``micc.json`` file can contain default values for the template parameters. "
                    "You will be prompted to provide a value for all parameters without default value. "
                    "*Micc* looks for the *micc-file* in the template directory **only** "
                    "(as specified with the ``--template`` option)."
                   )


@click.group()
@click.option('-v', '--verbosity', count=True
             , help="The verbosity of the program output."
             , default=1
             )
@click.option('-p', '--project-path'
             , help="The path to the project directory. "
                    "The default is the current working directory."
             , default='.'
             , type=Path
             )
@click.option('--clear-log'
             , help="If specified clears the project's ``micc.log`` file."
             , default=False, is_flag=True
             )
@click.pass_context
def main(ctx, verbosity, project_path, clear_log):
    """Micc command line interface.
    
    All commands that change the state of the project produce some output that
    is send to the console (taking verbosity into account). It is also sent to
    a logfile ``micc.log`` in the project directory. All output is always appended
    to the logfile. If you think the file has gotten too big, or you are no more
    interested in the history of your project, you can specify the ``--clear-log``
    flag to clear the logfile before any command is executed. In this way the
    command you execute is logged to an empty logfile.
    
    See below for (sub)commands.
    """
    if clear_log:
        os.remove(project_path / 'micc.log')
        
    ctx.obj = SimpleNamespace( verbosity=verbosity
                             , project_path=project_path.resolve()
                             , clear_log=clear_log
                             , template_parameters={}
                             )

#     if micc.utils.is_conda_python():
#         click.echo( click.style("==========================================================\n"
#                                 "WARNING: You are running in a conda Python environment.\n"
#                                 "         Note that poetry does not play well with conda.\n",   fg='yellow')
#                   + click.style("         Especially, do NOT use:\n"
#                                 "         >  poetry install\n",                                 fg='bright_red')
#                   + click.style("==========================================================\n", fg='yellow')
#                   )
    template_parameters_json = project_path / 'micc.json'
    if template_parameters_json.exists():
        ctx.obj.template_parameters.update(
            micc.expand.get_template_parameters(template_parameters_json)
        )
    else:
        ctx.obj.template_parameters.update(
            micc.expand.get_template_parameters(
                micc.expand.get_preferences(Path('.'))
            )
        )
    

@main.command()
@click.option('-p', '--package'
             , help="Create a Python project with a package structure rather than a module structure:\n\n"
                    "* package structure = ``<module_name>/__init__.py``\n"
                    "* module  structure = ``<module_name>.py`` \n"
             , default=False, is_flag=True
             )
@click.option('--micc-file'
             , help="The file containing the descriptions of the template parameters used"
                    "in the *Cookiecutter* templates. "
             , default='',type=Path
             )
@click.option('-d', '--description'
             , help="Short description of your project."
             , default='<Enter a one-sentence description of this project here.>'
             )
@click.option('-l', '--license'
             , help="Licence identifier."
             , default='MIT'
             )
@click.option('-T', '--template' , help=__template_help , default=[])
@click.option('-n', '--allow-nesting'
             , help="If specified allows to nest a project inside another project."
             , default=False, is_flag=True
             )
@click.pass_context
def create( ctx
          , package
          , micc_file
          , description
          , license
          , template
          , allow_nesting
          ):
    """Create a new project skeleton.
    
    The project name is taken to be the last directory of the *<project_path>*.
    If this directory does not yet exist, it is created. If it exists already, it
    must be empty.
    
    The package name is the derived from the project name, taking the
    `PEP8 module naming rules <https://www.python.org/dev/peps/pep-0008/#package-and-module-names>`_
    into account:
    
    * all lowercase.
    * dashes ``'-'`` and spaces ``' '`` replaced with underscores ``'_'``.
    * in case the project name has a leading number, an underscore is prepended ``'_'``.
    
    If no *<project_path>* is provided, or if it is the same as the current working
    directory, the user is prompted to enter one.
    
    If the *<project_path>* refers to an existing project, *micc* refuses to continu,
    unless ``--allow-nesting`` is soecified.
    """
    structure = 'package' if package else 'module'
    
    if not template: # default, empty list
        if structure=='module':
            template = ['package-base'
                       ,'package-simple'
                       ,'package-simple-docs'
                       ]
        else:
            template = ['package-base'
                       ,'package-general'
                       ,'package-simple-docs'
                       ,'package-general-docs'
                       ]
    else:
        # ignore structure
        structure = 'user-defined'
        
    ctx.obj.structure = structure
    ctx.obj.allow_nesting = allow_nesting
    licenses = ['MIT license'
               ,'BSD license'
               ,'ISC license'
               ,'Apache Software License 2.0'
               ,'GNU General Public License v3'
               ,'Not open source'
               ]
    for lic in licenses:
        if lic.startswith(license):
            license = lic
            break
    else:
        license = licenses[0]

    ctx.obj.template_parameters.update({'project_short_description' : description
                                       ,'open_source_license'       : license
                                       }
                                      ) 
                                        
    rc = cmds.micc_create( templates=template
                         , micc_file=micc_file
                         , global_options=ctx.obj
                         )
    if rc: ctx.exit(rc)

@main.command()
@click.option('--app'
             , default=False, is_flag=True
             , help="Add a CLI."
             )
@click.option('--group'
             , default=False, is_flag=True
             , help="Add a CLI with a group of sub-commands."
             )
@click.option('--py'
             , default=False, is_flag=True
             , help="Add a Python module."
             )
@click.option('--package'
             , help="Add a Python module with a package structure rather than a module structure:\n\n"
                    "* module  structure = ``<module_name>.py`` \n"
                    "* package structure = ``<module_name>/__init__.py``\n\n"
                    "Default = module structure."
             , default=False, is_flag=True
             )
@click.option('--f2py'
             , default=False, is_flag=True
             , help="Add a f2py binary extionsion module (Fortran)."
             )
@click.option('--cpp'
             , default=False, is_flag=True
             , help="Add a cpp binary extionsion module (C++)."
             )
@click.option('-T', '--template', default='', help=__template_help)
@click.option('--overwrite', is_flag=True
             , help="Overwrite pre-existing files (without backup)."
             , default=False
             )
@click.option('--backup', is_flag=True
             , help="Make backup files (.bak) before overwriting any pre-existing files."
             , default=False
             )
@click.argument('name',type=str)
@click.pass_context
def add( ctx
       , name
       , app, group
       , py, package
       , f2py
       , cpp
       , template
       , overwrite
       , backup
       ):
    """Add a module or CLI to the projcect.
    
    :param str name: name of the CLI or module added.
    
    If ``app==True``: (add CLI application)
    
    * :py:obj:`app_name` is also the name of the executable when the package is installed.
    * The source code of the app resides in :file:`<project_name>/<package_name>/cli_<name>.py`.


    If ``py==True``: (add Python module)
    
    * Python source  in :file:`<name>.py*`or :file:`<name>/__init__.py`, depending on the :py:obj:`package` flag.

    If ``f2py==True``: (add f2py module)
    
    * Fortran source in :file:`f2py_<name>/<name>.f90` for f2py binary extension modules.

    If ``cpp==True``: (add cpp module)
    
    * C++ source     in :file:`cpp_<name>/<name>.cpp` for cpp binary extension modules.
    """
    # set implied flags:
    if group:
        app_implied = f" [implied by --group   ({int(group  )})]"
        app = True
    else:
        app_implied = ""
        
    if package:
        py_implied  = f" [implied by --package ({int(package)})]"
        py = True
    else:
        py_implied = ""
    
    if not (app or py or f2py or cpp) or not xor(xor(app,py),xor(f2py,cpp)):
        click.secho(f"ERROR: specify one and only one of \n"
                    f"  --app  ({int(app )}){app_implied}\n"
                    f"  --py   ({int(py  )}){py_implied}\n"
                    f"  --f2py ({int(f2py)})\n"
                    f"  --cpp  ({int(cpp )})\n"
                   ,fg='bright_red'
                   )
    if app:
        if micc.utils.app_exists(ctx.obj.project_path, name):
            raise AssertionError(f"Project {ctx.obj.project_path.name} has already an app named {name}.")
    
        with micc.logging_tools.logtime(ctx.obj):
            if group:
                if not template:
                    template = 'app-sub-commands'
            else:
                if not template:
                    template = 'app-simple'
                    
            ctx.obj.overwrite = overwrite
            ctx.obj.backup    = backup
            ctx.obj.group     = group
            
            rc =  cmds.micc_app( name
                               , templates=template
                               , global_options=ctx.obj
                               )
    else:
        if micc.utils.module_exists(ctx.obj.project_path,name):
            raise AssertionError(f"Project {ctx.obj.project_path.name} has already a module named {name}.")

        ctx.obj.overwrite = overwrite
        ctx.obj.backup    = backup
        ctx.obj.template_parameters['path_to_cmake_tools'] = micc.utils.path_to_cmake_tools()
        
        if py:
            ctx.obj.structure = 'package' if package else 'module'
            if not template:
                template = 'module-py'
            rc = cmds.micc_module_py( name, templates=template, global_options=ctx.obj )
                    
        elif f2py:
            if not template:
                template = 'module-f2py'
            rc = cmds.micc_module_f2py( name, templates=template, global_options=ctx.obj )

        elif cpp:
            if not template:
                template = 'module-cpp'
            rc = cmds.micc_module_cpp( name, templates=template, global_options=ctx.obj )

    if rc:
        ctx.exit(rc)
    

@main.command()
@click.argument( 'rule', default='')
@click.option('-M','--major'
             , help='Increment the major version number component and set minor and patch components to 0.'
             , default=False, is_flag=True
             )
@click.option('-m','--minor'
             , help='Increment the minor version number component and set minor and patch component to 0.'
             , default=False, is_flag=True
             )
@click.option('-p','--patch'
             , help='Increment the patch version number component.'
             , default=False, is_flag=True
             )
@click.option('-t', '--tag'
             , help='Create a git tag for the new version, and push it to the remote repo.'
             , default=False, is_flag=True
             )
@click.option('-s', '--short'
             , help='Print the version on stdout.'
             , default=False, is_flag=True
             )
@click.option('--poetry'
             , help='Use poetry instead of bumpversion for bumping the version.'
             , default=False, is_flag=True
             )
@click.pass_context
def version( ctx, rule, major, minor, patch, tag, short, poetry):
    """Increment or show the project's version number.
    
    By default micc uses *bumpversion* for this, but it can also use *poetry*,
    by specifiying the ``--poetry`` flag.
    
    You can also avoide using ``micc version`` and use *bumpversion* directly. Note,
    however, that the version string appears in both ``pyproject.toml`` and in the top-level
    package (``<mopdule_name>.py`` or ``<mopdule_name>/__init__.py``). Since, currently,
    *poetry* is incapable of bumping the version string in any other file than *pyproject.tom.*,
    using ``poetry version ...`` is not recommented.
    
    :param str rule: any string that is also accepted by poetry version. Typically, the empty
        string (show current version), a valid rule: patch, minor, major, prepatch, preminor, 
        premajor, prerelease, or any valid version string.  
    """
    if rule and (major or minor or patch):
        raise RuntimeError("Ambiguous arguments:\n  specify either 'rule' argments,\n  or one of [--major,--minor--patch], not both.")

    if major:
        rule = 'major'
    if minor:
        rule = 'minor'
    if patch:
        rule = 'patch'
    
    with micc.logging_tools.logtime(ctx.obj):
        return_code = cmds.micc_version(rule, short, poetry, global_options=ctx.obj)
        if return_code==0 and tag:
            rc = cmds.micc_tag(global_options=ctx.obj)
        else:
            rc = return_code
    if rc: 
        ctx.exit(rc)


@main.command()
@click.pass_context
def tag(ctx):
    """Create a git tag for the current version and push it to the remote repo."""
    
    with micc.logging_tools.logtime(ctx.obj):
        return cmds.micc_tag(global_options=ctx.obj)


def _check_cxx_flags(cxx_flags,cli_option):
    """
    :param str cxx_flags: C++ compiler flags
    :param str cli_option: typically '--cxx-flags', or '--cxx-flags-all'.
    :raises: RunTimeError if cxx_flags starts or ends with a '"' but not both.
    """
    if cxx_flags.startswith('"') and cxx_flags.endswith('"'):
        # compile options appear between quotes
        pass
    elif not cxx_flags.startswith('"') and not cxx_flags.endswith('"'):
        # a singlecompile option must still be surrounded with quotes. 
        cxx_flags = f'"{cxx_flags}"'
    else:
        raise RuntimeError(f"{cli_option}: unmatched quotes: {cxx_flags}")
    return cxx_flags


def _check_load_save(filename,loadorsave):
    """
    :param str filename: possibly empty string.
    :param str loadorsave: 'load'|'save'.
    :raises: RunTimeError if filename is actually a file path.
    """
    if filename:
        if os.sep in filename:
            raise RuntimeError(f"--{loadorsave} {filename}: only filename allowed, not path.")
        if not filename.endswith('.json'):
            filename += '.json'
    return filename


@main.command()
@click.option('-m','--module'
             , help="Build only this module. The module kind prefix (``cpp_`` "
                    "for C++ modules, ``f2py_`` for Fortran modules) may be omitted."
             , default=''
             )
@click.option('-b','--build-type'
             , help="build type: For f2py modules, either RELEASE or DEBUG, where the latter"
                    "toggles the --debug, --noopt, and --noarch, and ignores all other "
                    "f2py compile flags. For cpp modules any of the standard CMake build types: "
                    "DEBUG, MINSIZEREL, RELEASE, RELWITHDEBINFO."
             , default='RELEASE'
             )
# F2py specific options
@click.option('--f90exec'
             , help="F2py: Specify the path to F90 compiler."
             , default=''
             )
@click.option('--f90flags'
             , help="F2py: Specify F90 compiler flags."
             , default='-O3'
             )
@click.option('--opt'
             , help="F2py: Specify optimization flags."
             , default='' 
             )
@click.option('--arch'
             , help="F2py: Specify architecture specific optimization flags."
             , default='' 
             )
@click.option('--debug'
             , help="F2py: Compile with debugging information."
             , default=False, is_flag=True
             )
@click.option('--noopt'
             , help="F2py: Compile without optimization."
             , default=False, is_flag=True
             )
@click.option('--noarch'
             , help="F2py: Compile without architecture specific optimization."
             , default=False, is_flag=True
             )
# Cpp specific options
@click.option('--cxx-compiler'
             , help="CMake: specify the C++ compiler (sets CMAKE_CXX_COMPILER)."
             , default=''
             )
@click.option('--cxx-flags'
             , help="CMake: set CMAKE_CXX_FLAGS_<built_type> to <cxx_flags>."
             , default=''
             )
@click.option('--cxx-flags-all'
             , help="CMake: set CMAKE_CXX_FLAGS_<built_type> to <cxx_flags>."
             , default=''
             )
# Other options
@click.option('--clean'
             , help="Perform a clean build."
             , default=False, is_flag=True
             )
@click.option('--load'
             , help="Load the build options from a (.json) file in the module directory. "
                    "All other compile options are ignored."
             , default=''
             )
@click.option('--save'
             , help="Save the build options to a (.json) file in the module directory."
             , default=''
             )
@click.option('-s', '--soft-link'
             , help="Create a soft link rather than a copy of the binary extension module."
             , default=False, is_flag=True
             )
@click.pass_context
def build( ctx, module
         , build_type
# F2py specific options
         , f90exec
         , f90flags, opt, arch
         , debug, noopt, noarch
# Cpp specific options
         , cxx_compiler
         , cxx_flags, cxx_flags_all
# Other options
         , clean
         , soft_link
         , load, save
         ):
    """Build binary extension libraries (f2py and cpp modules)."""
    if save:
        if os.sep in save:
            raise RuntimeError(f"--save {save}: only filename allowed, not path.")
        if not save.endswith('.json'):
            save += '.json'
    if load:
        if os.sep in load:
            raise RuntimeError(f"--load {load}: only filename allowed, not path.")
        if not load.endswith('.json'):
            load += '.json'
    
    with micc.logging_tools.logtime(ctx.obj):            
        build_options=SimpleNamespace( build_type = build_type.upper() )
        build_options.clean = clean
        build_options.soft_link = soft_link
        build_options.save = _check_load_save(save, "save")
        build_options.load = _check_load_save(load, "load")
        if not load:
            if build_type=='DEBUG':
                f2py = {'--debug' :None
                       ,'--noopt' :None
                       ,'--noarch':None
                       }
            else:
                f2py = {}
                if f90exec:
                    f2py['--f90exec'] = f90exec
                if f90flags:
                    f2py['--f90flags'] = f90flags
                if opt:
                    f2py['--opt'] = opt
                if arch:
                    f2py['--arch'] = arch
                if noopt:
                    f2py['--noopt'] = None
                if noarch:
                    f2py['--noarch'] = None
                if debug:
                    f2py['--debug'] = None
            build_options.f2py = f2py
    
            cmake = {}
            cmake['CMAKE_BUILD_TYPE'] = build_type
            if cxx_compiler:
                path_to_cxx_compiler = Path(cxx_compiler).resolve()
                if not path_to_cxx_compiler.exists():
                    raise FileNotFoundError(f"C++ compiler {path_to_cxx_compiler} not found.")
                cmake['CMAKE_CXX_COMPILER'] = str(path_to_cxx_compiler)
            if cxx_flags:
                cmake[f"CMAKE_CXX_FLAGS_{build_type}"] = _check_cxx_flags(cxx_flags,"--cxx-flags")
            if cxx_flags_all:
                cmake["CMAKE_CXX_FLAGS"] = _check_cxx_flags(cxx_flags_all,"--cxx-flags-all")
            build_options.cmake = cmake
            
        ctx.obj.build_options = build_options
        
        rc = cmds.micc_build( module_to_build=module
                            , global_options=ctx.obj
                            )
    if rc:
        ctx.exit(rc)
      

@main.command()
@click.option('--overwrite', is_flag=True
             , help="Overwrite pre-existing files (without backup)."
             , default=False
             )
@click.option('--backup', is_flag=True
             , help="Make backup files (.bak) before overwriting any pre-existing files."
             , default=False
             )
@click.pass_context
def convert_to_package(ctx, overwrite, backup):
    """Convert a Python module project to a package.

    A Python *module* project has only a ``<package_name>.py`` file, whereas
    a Python *package* project has ``<package_name>/__init__.py`` and can contain
    submodules, such as Python modules, packages and applications, as well as
    binary extension modules.

    This command also expands the ``package-general-docs`` template in this
    project, which adds a ``AUTHORS.rst``, ``HISTORY.rst`` and ``installation.rst``
    to the documentation structure.
    """

    with micc.logging_tools.logtime(ctx.obj):
        ctx.obj.overwrite = overwrite
        ctx.obj.backup    = backup
        rc = cmds.micc_convert_simple(global_options=ctx.obj)
        if rc==micc.expand.EXIT_OVERWRITE:
            micc.logging_tools.get_micc_logger(ctx.obj).warning(
                f"It is normally ok to overwrite 'index.rst' as you are not supposed\n"
                f"to edit the '.rst' files in '{ctx.obj.project_path}{os.sep}docs.'\n"
                f"If in doubt: rerun the command with the '--backup' flag,\n"
                f"  otherwise: rerun the command with the '--overwrite' flag,\n"
            )
    if rc:
        ctx.exit(rc)


@main.command()
@click.option('-h', '--html'
             , help="If specified builds html documentation."
             , default=False, is_flag=True
             )
@click.option('-l', '--latexpdf'
             , help="If specified builds pdf documentation."
             , default=False, is_flag=True
             )
@click.pass_context
def docs(ctx, html, latexpdf):
    """Build documentation for the project using Sphinx with the specified formats."""
    
    with micc.logging_tools.logtime(ctx.obj):
        formats = []
        if html:
            formats.append('html')
        if latexpdf:
            formats.append('latexpdf')
        
        rc = cmds.micc_docs(formats, global_options=ctx.obj)
    if rc:
        ctx.exit(rc)


@main.command()
@click.pass_context
def info(ctx):
    """Show project info.
        
    * file location
    * name
    * version number
    * structure (with ``-v``)
    * contents (with ``-vv``)
    
    Use verbosity to produce more detailed info.
    """    
    rc = cmds.micc_info(global_options=ctx.obj)
    if rc:
        ctx.exit(rc)


@main.command()
@click.argument('args',nargs=-1)
@click.option('--system'
             , help="Use the poetry version installed in the system, instead "
                    "of that in the python environment."
             , default=False, is_flag=True
             )
@click.pass_context
def poetry(ctx,args,system):
    """A wrapper around poetry that warns for dangerous poetry commands in a conda environment."""
    with micc.logging_tools.logtime(ctx.obj):
        ctx.obj.system = system
        rc = cmds.micc_poetry( *args, global_options=ctx.obj)
    if rc:
        ctx.exit(rc)

    
if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover