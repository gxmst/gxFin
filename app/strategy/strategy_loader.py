import os
import importlib.util
import inspect
import sys
import ast
from .base_strategy import BaseStrategy

class StrategyLoader:
    """
    Handles dynamic discovery and loading of strategy classes.
    SECURITY NOTE: The AST scan (_is_safe) is a best-effort static linter to catch basic mistakes
    and obvious malicious patterns. It does NOT provide a secure sandbox.
    Any .py file loaded here is executed via exec_module() and runs in the host environment.
    Use OS-level isolation (e.g. Docker) when loading untrusted strategies.
    """
    def __init__(self, strategies_dir="strategies"):
        self.strategies_dir = strategies_dir
        self.strategies = {}

    def _is_safe(self, file_path):
        """
        Perform a basic AST scan to prevent dangerous imports in strategies.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            
            # High-risk modules and builtins
            forbidden_modules = {'os', 'sys', 'subprocess', 'shutil', 'socket', 'requests', 'urllib'}
            forbidden_funcs = {'eval', 'exec', '__import__', 'getattr', 'setattr', 'compile', 'open'}
            
            for node in ast.walk(tree):
                # Check imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    names = node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module, asname=None)]
                    for alias in names:
                        if alias.name.split('.')[0] in forbidden_modules:
                            return False, f"Forbidden module: {alias.name}"
                
                # Check function calls
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in forbidden_funcs:
                        return False, f"Forbidden function call: {node.func.id}"
            return True, ""
        except Exception as e:
            return False, f"AST Parse error: {e}"

    def load_all(self):
        """
        Scan the strategies directory and load all valid strategy classes.
        """
        self.strategies = {}
        if not os.path.exists(self.strategies_dir):
            os.makedirs(self.strategies_dir)

        # Add strategy dir to sys.path to allow imports within strategies
        if os.path.abspath(self.strategies_dir) not in sys.path:
            sys.path.append(os.path.abspath(self.strategies_dir))

        for filename in os.listdir(self.strategies_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]
                file_path = os.path.join(self.strategies_dir, filename)
                
                # Security Check
                is_safe, reason = self._is_safe(file_path)
                if not is_safe:
                    print(f"Skipping unsafe strategy {filename}: {reason}")
                    continue

                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseStrategy) and 
                            obj is not BaseStrategy):
                            # Use either the class 'name' attribute or the class name
                            strategy_key = getattr(obj, "name", name)
                            self.strategies[strategy_key] = obj
                except Exception as e:
                    print(f"Error loading strategy from {filename}: {e}")
        
        return self.strategies

    def get_strategy_class(self, name):
        if not self.strategies:
            self.load_all()
        return self.strategies.get(name)

    def list_strategies(self):
        if not self.strategies:
            self.load_all()
        return list(self.strategies.keys())
