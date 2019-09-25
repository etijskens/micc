# -*- coding: utf-8 -*-
"""
Main module.
"""
#===============================================================================
import os
import sysconfig
import json
import subprocess
import shutil
import platform
import copy
import logging,sys
from pathlib import Path
#===============================================================================
import click
from cookiecutter.main import cookiecutter

from poetry.console.application import Application
from cleo.inputs.argv_input import ArgvInput
from poetry.utils.toml_file import TomlFile
from poetry.console.commands import VersionCommand 
import toml

from micc import utils
from micc.utils import in_directory

micc_logger = None

EXIT_CANCEL = -1 # exit code used for action EXIT_CANCELled by user


def exit_msg(exit_code):
    if exit_code==EXIT_CANCEL:
        micc_logger.warning("Command canceled, exiting!")
    elif exit_code!=0:
        micc_logger.error(f"Error {exit_code}, exiting!")
    return exit_code


def resolve_template(template):
    """
    """
    if  template.startswith('~') or template.startswith(os.sep):
        pass # absolute path
    elif os.sep in template:
        # reative path
        template = Path.cwd() / template
    else:
        # just the template name 
        template = Path(__file__).parent / template
    assert template.exists(), f"Inexisting template {template}"
    return template


def get_template_parameters(template, micc_file, **kwargs):
    """
    Read the template parameter descriptions from the micc file, and
    prompt the user for supplying the values for the parameters with an
    empty string as default.     
    
    :param Path template:
    
    :returns: a dict of (parameter,value) pairs.
    """
    micc_file = template / micc_file
    try:
        f = open(micc_file, 'r')
    except IOError:
        micc_logger.debug(f" . getting template parameters from (None)")
        template_parameters = {}
    else:
        with f:
            micc_logger.debug(f" . getting template parameters from {micc_file}.")
            template_parameters = json.load(f)
      
    for kw,arg in kwargs.items(): 
        template_parameters[kw] = {} 
        template_parameters[kw]['default'] = arg 
    
    for key,value in template_parameters.items():
        default = value['default']
        if bool(default):
            value = default
        else:
            kwargs = value
#             text = kwargs['text']
#             del kwargs['msg']
            if 'type' in kwargs:
                kwargs['type'] = eval(kwargs['type'])
            click.echo('')
            value = False
            while not value:
                value = click.prompt(**kwargs,show_default=False)
        template_parameters[key] = value

    micc_logger.debug(f" . parameters used:\n{json.dumps(template_parameters,indent=4)}")
    return template_parameters


def expand_templates(templates, micc_file, project_path, global_options, **extra_parameters):
    """
    Expand a list of cookiecutter ``templates`` in directory ``project_path``. 

    If ``global_options.overwrite==False`` it is verified that no files will be over
    written inadvertently. In that case you get the option to EXIT_CANCEL the command, 
    or overwrite the files with our without creating backup files. If, on the other
    hand, ``global_options.overwrite==true``, pre-existing files are overwritten
    without warning.
    
    :param list templates: ordered list of (paths to) cookiecutter templates that 
        will be expanded as they appear. The template parameters are propagated 
        from each template to the next.
    :param str micc_file: name of the micc file in all templates. Usually, this is
        ``'micc.json'``.
    :param Path project_path: path to the project directory where the templates 
        will be expanded
    :param types.SimpleNamespace: command line options accessible to all micc
        commands
    :param dict extra_parameters: extra template parameters that have to be set 
        before 
        expanding.
    """
    if not isinstance(templates, list):
        templates = [templates]
    project_path.mkdir(parents=True, exist_ok=True)
    output_dir = project_path.parent

    # get the template parameters,
    # list existing files that would be overwritten if global_options.overwrite==True
    existing_files = {}
    for template in templates:
        micc_logger.debug(f" . Expanding template {template} in temporary directory")
        template = resolve_template(template)             
        template_parameters = get_template_parameters( template, micc_file
                                                     , **extra_parameters
                                                     )
        # Store the template parameters from this template for the the next
        # template in the templates list
        extra_parameters = template_parameters
        # write a cookiecutter.json file in the cookiecutter template directory
        cookiecutter_json = template / 'cookiecutter.json'
        with open(cookiecutter_json,'w') as f:
            json.dump(template_parameters, f, indent=2)
        
        # run cookiecutter in an empty temporary directory to check if there are any
        # existing project files that woud be overwritten.
        if not global_options.overwrite:
            tmp = output_dir / '_cookiecutter_tmp_'
            if tmp.exists():
                shutil.rmtree(tmp)
            tmp.mkdir(parents=True, exist_ok=True)
    
            # expand the Cookiecutter template in a temporary directory,
            cookiecutter( str(template)
                        , no_input=True
                        , overwrite_if_exists=True
                        , output_dir=str(tmp)
                        )
            
            # find out if there are any files that would be overwritten.
            os_name = platform.system()
            for root, _, files in os.walk(tmp):
                if root==tmp:
                    continue
                else:
                    root2 = os.path.relpath(root,tmp)
                for f in files:
                    if os_name=="Darwin" and f==".DS_Store":
                        continue
                    file = output_dir / root2 / f
                    if file.exists():
                        if not template in existing_files:
                            existing_files[template] = []
                        existing_files[template].append(file)
    
        if existing_files:
            msg = f"The following pre-existing files will be overwritten in {output_dir}:\n"
            for template, files in existing_files.items():
                t = template.name
                for f in files:
                    msg += f"    {t} : {f}\n"
            micc_logger.warning(msg)
            answer = click.prompt("Press 'c' to continue\n"
                                  "      'a' to abort\n"
                                  "      'b' to keep the original files with .bak extension\n"
                                 ,type=click.Choice(['c', 'a','b'])
                                 ,default='a'
                                 ,show_choices=True
                                 ).lower()
            if answer=='a':
                micc_logger.critical("Exiting.")
                return EXIT_CANCEL,extra_parameters
            elif answer=='b':
                micc_logger.warning(f"Making backup files in {project_path}:")
                for files in existing_files.values():
                    for src in files:
                        dst = src + '.bak'
                        shutil.copyfile(src, dst)
                        micc_logger.warning(f"     created backup file: {dst}")
                micc_logger.warning(f"Overwriting files ...")
            else:
                micc_logger.warning("Overwriting files ... (no backup)")
            micc_logger.warning('Overwriting files ... Done.')
            
    # Now we can safely overwrite pre-existing files.
    for template in templates:
        template = resolve_template(template)
        micc_logger.debug(f" . Expanding template {template} in project directory.")
        cookiecutter( str(template)
                    , no_input=True
                    , overwrite_if_exists=True
                    , output_dir=str(output_dir)
                    )
        # Clean up (see issue #7)
        cookiecutter_json = template / 'cookiecutter.json'
        cookiecutter_json.unlink()

    # Clean up
    if tmp.exists():
        shutil.rmtree(str(tmp))
        
    return 0,extra_parameters


def msg_NotAProjectDirectory(path):
    return f"Invalid project directory {path}."


def msg_CannotAddToSimpleProject(path):
    return f"Cannot add components to simple project ({path})."


def msg_NotAPackageProject(path):
    return f"Not a package project ({path})."
    
def micc_create( templates
               , micc_file
               , global_options
               ):
    """
    Create a new project skeleton for a general Python project. This is a
    Python package with a ``<package_name>/__init__.py`` structure, to wich 
    other modules and applications can be added.
    
    :param str templates: ordered list of paths to a Cookiecutter_ template. a single 
        path is ok too.
    :param str micc_file: name of the json file with the default values in the template directories. 
    :param types.SimpleNamespace global_options: namespace object with options accepted by (almost) all micc commands. 
    """
    project_path = global_options.project_path
    project_path.mkdir(parents=True,exist_ok=True)
    output_dir = project_path.parent
    project_name  = project_path.name
    
    if global_options.structure=='module':
        structure = f" ({project_name}.py)" 
    elif global_options.structure=='package':
        structure = f" ({project_name}/__init__.py)"
    else:
        structure = '' 

    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.log(micc_logger.info, f"Creating Python package '{project_name}' as a {global_options.structure}{structure}"):
        project_path = output_dir / project_name
        assert not utils.is_project_directory(project_path),f"Project {project_path} exists already."
        # Prevent the creation of a project inside another project    
        # (add a 'dummy' leaf so the first directory checked is output_dir itself)
        if not global_options.allow_nesting:
            p = copy.copy(output_dir)
            while not p.samefile('/'):
                assert not utils.is_project_directory(p),f"Cannot create a project inside another project ({p})."
                p = p.parent
            
        global_options.overwrite = False
     
        ( exit_code
        , template_parameters
        ) = expand_templates( templates, micc_file, project_path, global_options
                            # extra template parameters:
                            , project_name=project_name
                            )                
        if exit_code:
            return exit_msg(exit_code)

        with utils.log(micc_logger.info,"Creating git repository"):
            with utils.in_directory(project_path):
                cmds = [ ['git', 'init']
                       , ['git', 'add', '*']
                       , ['git', 'add', '.gitignore']
                       , ['git', 'commit', '-m', '"first commit"']
                       , ['git', 'remote', 'add', 'origin', f"https://github.com/{template_parameters['github_username']}/{project_name}"]
                       , ['git', 'push', '-u', 'origin', 'master']
                       ]
                utils.execute(cmds, micc_logger.debug, stop_on_error=False)
                for cmd in cmds:
                    cmdstr = ' '.join(cmd)
                    with utils.log(micc_logger.debug, f'> {cmdstr}', end_msg=None):
                        completed_process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        if completed_process.stdout:
                            micc_logger.debug(' (stdout)\n' + completed_process.stdout.decode('utf-8'))
                        if completed_process.stderr:
                            micc_logger.debug(' (stderr)\n' + completed_process.stderr.decode('utf-8'))
    
    return 0


def micc_app( app_name
            , templates
            , micc_file
            , global_options
            ):
    """
    Micc app subcommand, add a console script (app) to the package. 
    
    :param str app_name: name of the applicatiom to be added.
    :param str templates: ordered list of paths to a Cookiecutter_ template. a 
        single path is ok too.
    :param str micc_file: name of the json file with the default values in the 
        template directories. 
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path), msg_NotAProjectDirectory(project_path)
    assert not utils.is_module_project(project_path), msg_CannotAddToSimpleProject(project_path)
    
    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.log(micc_logger.info, f"Creating app {app_name} in Python package {project_path.name}."):
    
        ( exit_code
        , _ # template_parameters
        ) = expand_templates( templates, micc_file, project_path, global_options
                            # extra template parameters:
                            , project_name=project_path.name
                            , package_name=utils.convert_to_valid_module_name(project_path.name)
                            , app_name=app_name
                            )                
        if exit_code:
            micc_logger.critical(f"Exiting ({exit_code}) ...")
            return exit_code
    
        with in_directory(project_path):
            cli_app_name = 'cli_' + utils.convert_to_valid_module_name(app_name)
            package_name =          utils.convert_to_valid_module_name(project_path.name)
            
            # docs 
            with open('docs/api.rst',"r") as f:
                lines = f.readlines()
            has_already_apps = False
            for line in lines:
                has_already_apps = has_already_apps or line.startswith(".. include:: ../APPS.rst")
            if not has_already_apps:        
                with open('docs/api.rst',"w") as f:
                    f.write(".. include:: ../APPS.rst\n\n")
                    f.write(".. include:: ../API.rst\n\n")
            with open("APPS.rst","a") as f:
                f.write(f".. automodule:: {package_name}.{cli_app_name}\n")
                f.write( "   :members:\n\n")
            micc_logger.debug(f" . documentation for application '{app_name}' added.")
            
            # pyproject.toml
            # in the [toolpoetry.scripts] add a line 
            #    {app_name} = "{package_name}:{cli_app_name}"
            tomlfile = TomlFile('pyproject.toml')
            content = tomlfile.read()
            content['tool']['poetry']['scripts'][app_name] = f'{package_name}:{cli_app_name}'
            tomlfile.write(content)

    return 0


def micc_module_py( module_name
                  , templates
                  , micc_file
                  , global_options
                  ):
    """
    ``micc module`` subcommand, add a Python module to the package. 
    
    :param str module_name: name of the module to be added.
    :param bool simple: create simple (``<module_name>.py``) or general python module 
    :param str templates: ordered list of paths to a Cookiecutter_ template. a 
        single path is ok too.
    :param str micc_file: name of the json file with the default values in the 
        template directories. 
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path), msg_NotAProjectDirectory(project_path)
    assert not utils.is_module_project(project_path), msg_CannotAddToSimpleProject(project_path)
    assert     utils.is_package_project(project_path), msg_NotAPackageProject(project_path)
    assert module_name==utils.convert_to_valid_module_name(module_name), f"Not a valid module_name {module_name}" 

    package_name = utils.convert_to_valid_module_name(project_path.name)
    global_options.module_kind = 'python module'
    
    source_file = f"{module_name}.py" if global_options.structure=='module' else f"{module_name}/__init__.py"
    
    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.log(micc_logger.info,f"Creating python module {source_file} in Python package {project_path.name}."):
        
        ( exit_code
        , _ #template_paraeters
        ) = expand_templates( templates, micc_file, project_path, global_options
                            # extra template parameters:
                            , project_name=project_path.name
                            , package_name=package_name
                            , module_name=module_name
                            )
        if exit_code:
            micc_logger.critical(f"Exiting ({exit_code}) ...")
            return exit_code
        
        if global_options.structure=='package':
            module_to_package(project_path / package_name / (module_name + '.py'))

        with in_directory(project_path):    
            # docs
            with open("API.rst","a") as f:
                f.write(f"\n.. automodule:: {package_name}.{module_name}"
                         "\n   :members:\n\n"
                       )
            utils.log(micc_logger.debug,f" . documentation entries for Python module {module_name} added.")
    return 0


def micc_module_f2py( module_name
                    , templates
                    , micc_file
                    , global_options
                    ):
    """
    ``micc module --f2py`` subcommand, add a f2py module to the package. 
    
    :param str module_name: name of the module to be added.
    :param str templates: ordered list of paths to a Cookiecutter_ template. a 
        single path is ok too.
    :param str micc_file: name of the json file with the default values in the 
        template directories. 
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path), msg_NotAProjectDirectory(project_path)
    assert not utils.is_module_project(project_path), msg_CannotAddToSimpleProject(project_path)
    assert     utils.is_package_project(project_path), msg_NotAPackageProject(project_path)
    assert module_name==utils.convert_to_valid_module_name(module_name), f"Not a valid module_name {module_name}" 

    package_name = utils.convert_to_valid_module_name(project_path.name)
    global_options.module_kind = 'f2py module'
    
    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.log(micc_logger.info,f"Creating f2py module f2py_{module_name} in Python package {project_path.name}."):
        
        ( exit_code
        , _ #template_paraeters
        ) = expand_templates( templates, micc_file, project_path, global_options
                            # extra template parameters:
                            , project_name=project_path.name
                            , package_name=package_name
                            , module_name=module_name
                            , path_to_cmake_tools=utils.path_to_cmake_tools()
                            )
        if exit_code:
            micc_logger.critical(f"Exiting ({exit_code}) ...")
            return exit_code
            
        with in_directory(project_path):
            # docs
            with open("API.rst","a") as f:
                f.write(f"\n.. include:: ../{package_name}/f2py_{module_name}/{module_name}.rst\n")
            micc_logger.warning(f" .  Documentation template for f2py module '{module_name}' added.\n"
                                f"    Because recent versions of sphinx are incompatible with sphinxfortran,\n"
                                f"    you are required to enter the documentation manually in file\n"
                                f"    '{project_path.name}/{package_name}/{module_name}.rst' in reStructuredText format.\n"
                                f"    A suitable example is pasted.\n"
                               )
    return 0


def micc_module_cpp( module_name
                   , templates
                   , micc_file
                   , global_options
                   ):
    """
    ``micc module --cpp`` subcommand, add a C++ module to the package. 
    
    :param str module_name: name of the module to be added.
    :param str templates: ordered list of paths to a Cookiecutter_ template. a 
        single path is ok too.
    :param str micc_file: name of the json file with the default values in the 
        template directories. 
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path), msg_NotAProjectDirectory(project_path)
    assert not utils.is_module_project(project_path), msg_CannotAddToSimpleProject(project_path)
    assert     utils.is_package_project(project_path), msg_NotAPackageProject(project_path)
    assert module_name==utils.convert_to_valid_module_name(module_name), f"Not a valid module_name {module_name}" 

    package_name = utils.convert_to_valid_module_name(project_path.name)
    global_options.module_kind = 'f2py module'
    
    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.log(micc_logger.info,f"Creating f2py module f2py_{module_name} in Python package {project_path.name}."):
        
        ( exit_code
        , _ #template_paraeters
        ) = expand_templates( templates, micc_file, project_path, global_options
                            # extra template parameters:
                            , project_name=project_path.name
                            , package_name=package_name
                            , module_name=module_name
                            , path_to_cmake_tools=utils.path_to_cmake_tools()
                            )
        if exit_code:
            micc_logger.critical(f"Exiting ({exit_code}) ...")
            return exit_code

        with in_directory(project_path):
            # docs
            with open("API.rst","a") as f:
                f.write(f"\n.. include:: ../{package_name}/cpp_{module_name}/{module_name}.rst\n")
            micc_logger.warning(f"    Documentation template for cpp module '{module_name}' added.\n"
                                f"    Because recent versions of sphinx are incompatible with sphinxfortran,\n"
                                f"    you are required to enter the documentation manually in file\n"
                                f"    '{project_path.name}/{package_name}/{module_name}.rst' in reStructuredText format.\n"
                                f"    A suitable example is pasted.\n"
                               )
    return 0


def micc_version( rule, global_options):
    """
    Bump the version according to *rule*, and modify the pyproject.toml in 
    *project_path*.
    
    :param str rule: one of the valid arguments for the ``poetry version <rule>``
        command.
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path),msg_NotAProjectDirectory(project_path)

    project_path = Path(project_path)
    pyproject_toml = toml.load(str(project_path /'pyproject.toml'))
    project_name    = pyproject_toml['tool']['poetry']['name']
    current_version = pyproject_toml['tool']['poetry']['version']
    package_name    = utils.convert_to_valid_module_name(project_name)

    global micc_logger
    if rule is None:
        micc_logger = utils.get_micc_logger(verbosity=2)
        micc_logger.info(f"Current version: {project_name} v{current_version}")
    else:
        micc_logger = utils.get_micc_logger(global_options)
        new_version = VersionCommand().increment_version(current_version, rule)
        msg = (f"Package {project_name} v{current_version}\n"
               f"Are you sure to move to v{new_version}'?")
        micc_logger.warning(msg)
        if not click.confirm("Confirm to continue",default=False):
            micc_logger.warning(f"EXIT_CANCELed: 'micc version {rule}'")
            return EXIT_CANCEL
        micc_logger.warning(f"{project_name} v{current_version} -> v{new_version}")

        # wrt poetry issue #1182. This issue is finally solved, boils down to 
        # tomlkit expecting the sections to appear grouped in pyproject.toml.
        # Our pyproject.toml contained a [tool.poetry.scripts] section AFTER 
        # the [build-system] section. when running E.g. poetry --version patch 
        # the version stringiest is NOT updated, but pyproject.toml is REWRITTEN
        # and now the [tool.poetry.scripts] section appears BEFORE the [build-system] 
        # section, nicely grouped with the other [tool.poetry.*] sections. Running 
        # poetry --version patch a second time then updates the version string 
        # correctly. 
        # This took me quite a few days find out ...
         
        # update version in pyproject.toml (using poetry code for good :)
        with utils.in_directory(project_path): 
            i = ArgvInput(['poetry','version',rule])
            app = Application()
            app._auto_exit = False
            app.run(i)       
        micc_logger.debug(' . Updating : pyproject.toml)')
            
        # update version in package
        files = [ project_path / package_name / '__init__.py'
                , project_path / (package_name + '.py')
                ]
        for f in files:
            if f.exists():
                with utils.log(micc_logger.debug, f" . Updating {f.name}"):
                    utils.replace_version_in_file( f, current_version, new_version)
    return 0


def micc_tag( global_options):
    """
    Create and push a version tag ``vM.m.p`` for the current version.
    
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path),msg_NotAProjectDirectory(project_path)
            
    path_to_pyproject_toml = project_path / 'pyproject.toml'
    pyproject_toml = toml.load(str(path_to_pyproject_toml))
    project_name    = pyproject_toml['tool']['poetry']['name']
    current_version = pyproject_toml['tool']['poetry']['version']
    tag = f"v{current_version}"

    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    
    with utils.in_directory(project_path):
    
        micc_logger.info(f"Creating git tag {tag} for project {project_name}")
        cmd = ['git', 'tag', '-a', tag, '-m', f'"tag version {current_version}"']
        micc_logger.debug(f"Running '{' '.join(cmd)}'")
        completed_process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        micc_logger.debug(completed_process.stdout.decode('utf-8'))
        if completed_process.stderr:
            micc_logger.critical(completed_process.stderr.decode('utf-8'))

        micc_logger.debug(f"Pushing tag {tag} for project {project_name}")
        cmd = ['git', 'push', 'origin', tag]
        micc_logger.debug(f"Running '{' '.join(cmd)}'")
        completed_process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        micc_logger.debug(completed_process.stdout.decode('utf-8'))
        if completed_process.stderr:
            micc_logger.error(completed_process.stderr.decode('utf-8'))
            
    micc_logger.info('Done.')
    return 0


def micc_build( module_to_build
              , soft_link
              , global_options
              ):
    """
    Build all binary extions, i.e. f2py modules and cpp modules.
    
    :param str module_to_build: name of the only module to build (the prefix cpp_ or f2py_ may be omitted)
    :param bool soft_link: if False, the binary extension modules are copied
        into the package directory. Otherwise a soft link is provided.
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path),msg_NotAProjectDirectory(project_path)
    
    package_path = project_path / utils.convert_to_valid_module_name(project_path.name)
        
    # get extension for binary extensions (depends on OS and python version)
    extension_suffix = utils.get_extension_suffix()

    dirs = os.listdir(package_path)
    for d in dirs:
        if (     (package_path / d).is_dir() 
             and (d.startswith("f2py_") or d.startswith("cpp_"))
           ):
            if module_to_build and not d.endswith(module_to_build): # build only this module
                continue

            filepath = project_path / f"micc-build-{d}.log"
            build_logger = utils.create_logger(filepath, filemode='w')
 
            module_type,module_name = d.split('_',1)
            build_dir = package_path / d / 'build_'
            build_dir.mkdir(parents=True, exist_ok=True)

            with utils.log(build_logger.info,f"\nBuilding {module_type} module {module_name} in directory '{build_dir}'"):
                with utils.in_directory(build_dir):
                    cextension = module_name + extension_suffix
                    destination = (Path('../../') / cextension).resolve()
                    cmds = [ ['cmake','CMAKE_BUILD_TYPE','=','RELEASE', '..']
                           , ['make']
                           ]
                    if soft_link:
                        cmds.append(['ln', '-sf', str(cextension), str(destination)])
                    else:
                        if destination.exists():
                            build_logger.debug(f">>> os.remove({destination})\n")
                            destination.unlink()
                    # WARNING: for these commands to work in eclipse, eclipse must have
                    # started from the shell with the appropriate environment activated.
                    # Otherwise subprocess starts out with the wrong environment. It 
                    # may not pick the right Python version, and may not find pybind11.
                    returncode = utils.execute(cmds, build_logger.debug, stop_on_error=True, env=os.environ.copy())
                    if not returncode:
                        if not soft_link:
                            build_logger.debug(f">>> shutil.copyfile( '{cextension}', '{destination}' )\n")
                            shutil.copyfile(cextension, destination)
            build_logger.info(f"Check {filepath.name} for details.\n")

    return 0


def module_to_package(module_py):
    """
    Move file module.py to module/__init__.py
    
    :param str|Path module_py
    
    """
    if not isinstance(module_py, Path):
        module_py = Path(module_py)
    if not module_py.is_file():
        raise FileNotFoundError(module_py)
    src = str(module_py.resolve())
    
    package_name = str(module_py.name).replace('.py','')
    package = module_py.parent / package_name
    package.mkdir()
    dst = str(package / '__init__.py')
    shutil.move(src, dst)
    utils.log(micc_logger.debug,f" . Module {module_py} converted to package {package_name}{os.sep}__init__.py.")


def micc_convert_simple(global_options):
    """
    Convert simple python package to general python package.

    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert utils.is_project_directory(project_path),msg_NotAProjectDirectory(project_path)
    assert not utils.is_module_project(project_path), msg_CannotAddToSimpleProject(project_path)
    assert     utils.is_package_project(project_path), msg_NotAPackageProject(project_path)
    
    if global_options.verbosity>0:
        click.echo(f"Converting simple Python project {project_path.name} to general Python project.")
    
    # add documentation files for general Python project
    tomlfile = TomlFile('pyproject.toml')
    content = tomlfile.read()

    ( exit_code
    , _ # template_parameters
    ) = expand_templates("template-package-general-docs", 'micc.json', project_path, global_options
                        # extra template parameters:
                        , project_name=project_path.name
                        , project_short_description=content['tool']['poetry']['description']
                        )                
    if exit_code:
        return exit_code
    
    package_name = utils.convert_to_valid_module_name(project_path.name)
    package_path = project_path / package_name
    os.makedirs(package_path)
    src = project_path /(package_name + '.py')
    dst = project_path / package_name / '__init__.py'
    shutil.move(src, dst)
    
    return 0


def micc_docs(formats, global_options):
    """
    Build documentation for the project.
    :param list formats: list of formats to build documentation with. Valid
        formats are ``'html'``, ``'latexpdf'``.
    :param types.SimpleNamespace global_options: namespace object with options 
        accepted by (almost) all micc commands.
    """
    project_path = global_options.project_path
    assert formats, "No documentation format specified. "
    cmds = []
    for fmt in formats:
        cmds.append(['make',fmt])
        
    global micc_logger
    micc_logger = utils.get_micc_logger(global_options)
    with utils.in_directory(project_path / 'docs'):
        with utils.log(micc_logger.info,f"Building documentation for project {project_path.name}."):
            utils.execute(cmds, micc_logger.debug, env=os.environ.copy())
        
# EOF #