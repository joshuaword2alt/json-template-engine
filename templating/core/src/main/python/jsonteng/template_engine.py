# Copyright 2019 VMware, Inc.
# SPDX-License-Indentifier: Apache-2.0

import argparse
import datetime
import os
import json
from collections import OrderedDict
from importlib import import_module

from jsonteng.element_resolver import ElementResolver
from jsonteng.rules.rule_map import add_rule, get_rule_names
from jsonteng.stats import Stats
from jsonteng.json_loader import DefaultJsonLoader
from jsonteng.util import (unescape_json, check_duplicated_binding_data)


class JsonTemplateEngine(object):
    """
    `JsonTemplateEngine` class resolves templates by parameter expansions.
    """
    def __init__(self, env=None, template_loader=None):
        """
        Construct a new `JsonTemplateEngine`.
        :param env: A JSON object in the string format providing binding data.
                    It is placed at the end of the parameter resolution order.
        :type env: 'str'
        :param template_loader: A template loader for loading and unloading
                                templates used by the main template directly
                                or indirectly.
        :type template_loader: 'str'
        """
        self._env = env
        if template_loader is not None:
            self._template_loader = template_loader
        else:
            self._template_loader = DefaultJsonLoader(
                os.environ.get("TEMPLATE_HOME"))
        self._dup_params = OrderedDict()
        self._stats = Stats()
        self._element_resolver = ElementResolver(
            self._template_loader, self._stats)

    def resolve(self, main_template, binding_data_list):
        """
        Resolve a template.
        :param main_template: The main template to be resolved.
        :type main_template: 'str'
        :param binding_data_list: Binding data list
        :type binding_data_list: 'list'
        :return: resolved JSON object
        :rtype: JSON object
        """
        self._stats.clear()
        main_template_json = self._template_loader.load(main_template)
        effective_binding_data_list = binding_data_list
        if self._env:
            effective_binding_data_list.append(self._env)
        self._dup_params = check_duplicated_binding_data(
            effective_binding_data_list)

        resolved_json = self._element_resolver.resolve(
            main_template_json, effective_binding_data_list)
        self._template_loader.unload(main_template)
        return unescape_json(resolved_json)

    def get_duplicated_parameters(self):
        """
        Get duplicated parameters in the binding data list.
        :return: Duplicated parameters with the key to be the parameter name
                 and value to be a list of parameter values.
        :rtype: 'dict'
        """
        return self._dup_params

    def get_stats(self):
        """
        Get stats for parameter expansions.
        :return: a dictionary with key to be parameter name and value to be
                 number of times the parameter is expanded.
        :rtype: 'dict'
        """
        return self._stats.get_stats()

    @staticmethod
    def add_rules(rules):
        """
        Add a list of rules to supplement built-in rules.
        :param rules: A list of rules.
        :type rules: 'list'
        """
        for rule_class in rules:
            module_path, class_name = rule_class.rsplit('.', 1)
            module = import_module(module_path)
            class_object = getattr(module, class_name)
            add_rule(class_object.name, class_object)

    @staticmethod
    def list_rule_names():
        """
        Return a list of rule names.
        :return: Rule names.
        :rtype: 'list'
        """
        return get_rule_names()


def main(args=None):
    """
    CLI version of the template engine.
    """
    parser = argparse.ArgumentParser(description='JSON template engine.')
    parser.add_argument('-b', '--binding-data-resources', required=True,
                        help="a comma separated list of binding data"
                             " resource locators")
    parser.add_argument('-e', '--env', required=False,
                        help="global binding data")
    parser.add_argument('-v', '--verbose', required=False,
                        help="increase output verbosity",
                        action="store_true")
    parser.add_argument('-s', '--stats', required=False,
                        help="show stats",
                        action="store_true")
    parser.add_argument('-d', '--debug', required=False,
                        help="show debug info",
                        action="store_true")
    parser.add_argument('-r', '--raw', required=False,
                        help="unformatted output",
                        action="store_true")
    parser.add_argument('-u', '--rules', required=False,
                        help="common separated rule list")
    parser.add_argument('main_template')
    params = parser.parse_args(args=args)
    binding_file_list = params.binding_data_resources.split(';')
    binding_data_list = list()
    loader = DefaultJsonLoader()
    for binding_file in binding_file_list:
        binding_data = loader.load(binding_file)
        binding_data_list.append(binding_data)
        loader.unload(binding_file)
    env_binding = json.loads(
        params.env, object_pairs_hook=OrderedDict) if params.env else None
    main_template = params.main_template

    if params.debug:
        print("env data: {}".format(env_binding))
        print("binding data: {}".format(binding_data_list))
        print("main template: {}".format(main_template))

    if params.rules:
        rules = params.rules.split(',')
        JsonTemplateEngine.add_rules(rules)

    template_engine = JsonTemplateEngine(env_binding)
    start_time = datetime.datetime.now()
    resolved_json = template_engine.resolve(
        main_template, binding_data_list)
    end_time = datetime.datetime.now()
    if params.verbose:
        for dup_param in template_engine.get_duplicated_parameters():
            print("Warning: Parameter {} has duplicated values".
                  format(dup_param))
        delta = end_time - start_time
        print("Resolved JSON in {}".format(delta))
    if params.raw:
        print(json.dumps(resolved_json))
    else:
        print(json.dumps(resolved_json, indent=2))
    if params.stats:
        print("Parameter usage")
        param_map = template_engine.get_stats()
        print(json.dumps(param_map, indent=2, sort_keys=True))


# JsonTemplateEngine is primarily used as an embedded library. It can also be
# used as a CLI. The following section is for CLI support.
if __name__ == "__main__":
    main()