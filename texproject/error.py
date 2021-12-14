from .term import REPO_FORMATTED

class BuildError(Exception):
    def __init__(self, stderr, message="LaTeX build error."):
        self.stderr = stderr
        self.message = message
        super().__init__(self.message)

class BasePathError(Exception):
    def __init__(self, path, message="Error involving path."):
        self.path = path
        self.message = message
        super().__init__(self.message)

class DataMissingError(BasePathError):
    pass

class TemplateDataMissingError(DataMissingError):
    def __init__(self, path, user_str, name=None):
        if name is not None:
            message = f"The {user_str} '{name}' does not exist."
        else:
            message = f"The {user_str} does not exist."
        super().__init__(path, message=message)

class SystemDataMissingError(DataMissingError):
    def __init__(self, path):
        message = ("System data files are missing or not up to date. "
                f"See {REPO_FORMATTED} for more information.")

        super().__init__(path, message=message)

class ProjectDataMissingError(DataMissingError):
    pass

class ProjectMissingError(BasePathError):
    def __init__(self, path):
        message = f"The working directory is not a valid project."
        super().__init__(path, message=message)

class ProjectExistsError(BasePathError):
    def __init__(self, path):
        message = f"Conflicting files already exist in the working directory."
        super().__init__(path, message=message)

class GitMissingError(BasePathError):
    def __init__(self, path):
        message = f"The working directory is not a valid git repository."
        super().__init__(path, message=message)

class GitExistsError(BasePathError):
    def __init__(self, path):
        message = f"Conflicting git files already exist in the working directory."
        super().__init__(path, message=message)
