import julia
import os


class JuliaSystemImage:
    """
    This class manages compilation of a Julia system image.
    """
    def __init__(self,
                 name,
                 sys_image_dir, # Absolute, not relative path!
                 julia_version = None,
                 sys_image_file_base=None,
                 logger=None,
                 ):
        self.logger = logger
        self.sys_image_dir = sys_image_dir
        if sys_image_file_base is None:
            sys_image_file_base = "sys_" + name
        self.sys_image_file_base = sys_image_file_base
        self.julia_version = julia_version
        self.set_toml_paths()
        self.set_sys_image_paths()


    def _maybe_remove(self, path):
        if os.path.exists(path):
            os.remove(path)
            self.logger.info(f"Removing {path}")


    def _in_sys_image_dir(self, rel_path):
        """Return absolute path from path relative to system image build dir."""
        return os.path.join(self.sys_image_dir, rel_path)


    def get_sys_image_file_name(self):
        """Return the filename of the system image written upon compilation. This
        file will be renamed after compilation.
        """
        # self.version_raw = self.julia_info.version_raw # Make this a dict, or use JuliaInfo
        return self.sys_image_file_base + "-" + self.julia_version + julia.find_libpython.SHLIB_SUFFIX


    def set_sys_image_paths(self):
        self.sys_image_path = self._in_sys_image_dir(self.get_sys_image_file_name())
        self.compiled_system_image = self._in_sys_image_dir("sys_julia_project" + julia.find_libpython.SHLIB_SUFFIX)


    def set_toml_paths(self):
        self.sys_image_project_toml = self._in_sys_image_dir("Project.toml")
        self.sys_image_julia_project_toml = self._in_sys_image_dir("JuliaProject.toml")
        self.sys_image_manifest_toml = self._in_sys_image_dir("Manifest.toml")


    def clean(self):
        """
        Delete some files created when installing Julia packages. These are Manifest.toml files
        and a compiled system image.
        """
        for _file in [self.sys_image_manifest_toml, self.sys_image_path]:
            self._maybe_remove(_file)


    def compile(self):
        """
        Compile a system image for the dependent Julia packages in the subdirectory `./sys_image/`. This
        system image will be loaded the next time you import the Python module.
        """
        self.compile_julia_project()


    # TODO deprecate in favor of compile
    def compile_julia_project(self):
        from julia import Main, Pkg
        current_path = Main.pwd()
        current_project = Pkg.project().path
        try:
            self._compile_julia_project()
        except:
            print("Exception when compiling")
            raise
        finally:
            Main.cd(current_path)
            Pkg.activate(current_project)


    def _compile_julia_project(self):
        """
        Compile a Julia system image with all requirements for the julia project.
        """
        from julia import Main, Pkg
        logger = self.logger
        if not os.path.isdir(self._in_sys_image_dir("")):
            msg = f"Can't find directory for compiling system image: {self._in_sys_image_dir('')}"
            raise FileNotFoundError(msg)

        # self.set_sys_image_paths() # already done
        # TODO: Fix this
        # if self.loaded_sys_image_path == self.sys_image_path:
        #     for msg in ("WARNING: Compiling system image while compiled system image is loaded.",
        #                 f"Consider deleting  {self.sys_image_path} and restarting python."):
        #         print(msg)
        #         logger.warn(msg)
        if not (os.path.isfile(self.sys_image_project_toml) or os.path.isfile(self.sys_image_julia_project_toml)):
            msg = f"Neither \"{self.sys_image_project_toml}\" nor \"{self.sys_iamge_julia_project_toml}\" exist."
            logger.error(msg)
            raise FileNotFoundError(msg)
        self._maybe_remove(self.sys_image_manifest_toml)
        from julia import Pkg
        Main.eval('ENV["PYCALL_JL_RUNTIME_PYTHON"] = Sys.which("python")')
        Pkg.activate(self._in_sys_image_dir(""))
        logger.info("Compiling: probed Project.toml path: %s", Pkg.project().path)
        Main.cd(self._in_sys_image_dir(""))
        try:
            Pkg.resolve()
        except:
            msg = "Pkg.resolve() failed. Updating packages."
            print(msg)
            logger.info(msg)
            Pkg.update()
            Pkg.resolve()
        Pkg.instantiate()
        compile_script = "compile_julia_project.jl"
        logger.info(f"Running compile script {compile_script}.")
        Main.include(compile_script)
        if os.path.isfile(self.compiled_system_image):
            logger.info("Compiled image found: %s.", self.compiled_system_image)
            os.rename(self.compiled_system_image, self.sys_image_path)
            logger.info("Renamed compiled image to: %s.", self.sys_image_path)
            if not os.path.isfile(self.sys_image_path):
                logger.error("Failed renamed compiled image to: %s.", self.sys_image_path)
                raise FileNotFoundError(self.compiled_system_image)
        else:
            raise FileNotFoundError(self.compiled_system_image)
