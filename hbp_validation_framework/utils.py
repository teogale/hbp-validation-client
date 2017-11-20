"""
Miscellaneous methods that help in different aspects of model validation.
Does not require explicit instantiation.

The following methods are available:

====================================   ====================================
Action                                 Method
====================================   ====================================
View JSON data in web browser          :meth:`view_json_tree`
Run test and register result           :meth:`run_test`
====================================   ====================================
"""

import os
import json
import webbrowser
import argparse
import sciunit
from datetime import datetime
from . import TestLibrary, ModelCatalog
from .datastores import CollabDataStore


def view_json_tree(data):
    """Displays the JSON tree structure inside the web browser

    This method can be used to view any JSON data, generated by any of the
    validation client's methods, in a tree-like representation.

    Parameters
    ----------
    data : string
        JSON object represented as a string.

    Returns
    -------
    None
        Does not return any data. JSON displayed inside web browser.

    Examples
    --------
    >>> model = model_catalog.get_model(alias="HCkt")
    >>> from hbp_validation_framework import utils
    >>> utils.view_json_tree(model)
    """

    _make_js_file(data)

    script_dir = os.path.dirname(__file__)
    rel_path = "jsonTreeViewer/index.htm"
    abs_file_path = os.path.join(script_dir, rel_path)
    webbrowser.open(abs_file_path, new=2)

def _make_js_file(data):
    """
    Creates a JavaScript file from give JSON object; loaded by the browser
    This eliminates cross-origin issues with loading local data files (e.g. via jQuery)
    """

    script_dir = os.path.dirname(__file__)
    rel_path = "jsonTreeViewer/data.js"
    abs_file_path = os.path.join(script_dir, rel_path)
    with open(abs_file_path, 'w') as outfile:
        outfile.write("var data = '")
        json.dump(data, outfile)
        outfile.write("'")

def run_test(hbp_username="", model="", test_instance_id="", test_id="", test_alias="", test_version="", storage_collab_id="", register_result=True, model_metadata="", **test_kwargs):
    """Run validation test and register result

    This method will accept a model, located locally, run the specified
    test on the model, and store the results on the validation service.
    The test can be specified in the following ways (in order of priority):

    1. specify `test_instance_id` corresponding to test instance in test library
    2. specify `test_id` and `test_version`
    3. specify `test_alias` and `test_version`

    Parameters
    ----------
    hbp_username : string
        Your HBP collaboratory username.
    model : sciunit.Model
        A :class:`sciunit.Model` instance.
    test_instance_id : UUID
        System generated unique identifier associated with test instance.
    test_id : UUID
        System generated unique identifier associated with test definition.
    test_alias : string
        User-assigned unique identifier associated with test definition.
    test_version : string
        User-assigned identifier (unique for each test) associated with test instance.
    storage_collab_id : string
        Collab ID where output files should be stored; if empty, stored in model's host collab.
    register_result : boolean
        Specify whether the test results are to be scored on the validation framework.
        Default is set as True.
    model_metadata : dict
        Data for registering model in the model catalog. If the model already exists
        in the model catalog, then the model_instance UUID must be specified in the model's source
        code by setting `model.instance_id`. Otherwise, the model is registered using info from
        `model_metadata`. If `id` and `model_metadata` are both absent, then the results
        will not be saved on the validation framework (even if `register_result` = True).
    **test_kwargs : list
        Keyword arguments to be passed to the Test constructor.

    Note
    ----
    This is a very basic implementation that would suffice for simple use cases.
    You can customize and create your own run_test() implementations.

    Returns
    -------
    None
        Does not return any data.

    Examples
    --------
    >>> import models
    >>> from hbp_validation_framework import utils
    >>> mymodel = models.hippoCircuit()
    >>> utils.run_test(hbp_username="shailesh", model=mymodel, test_alias="CDT-5", test_version="5.0")
    """

    # Check the model
    if not isinstance(model, sciunit.Model):
        raise TypeError("`model` is not a sciunit Model!")
    print "----------------------------------------------"
    print "Model name: ", model
    print "Model type: ", type(model)
    print "----------------------------------------------"

    if not hbp_username:
        print "\n=============================================="
        print "Please enter your HBP username."
        hbp_username = raw_input('HBP Username: ')

    # Load the test
    test_library = TestLibrary(hbp_username)

    if test_instance_id == "" and (test_id == "" or test_version == "") and (test_alias == "" or test_version == ""):
        raise Exception("test_instance_id or (test_id, test_version) or (test_alias, test_version) needs to be provided for finding test.")
    else:
        test = test_library.get_validation_test(instance_id=test_instance_id, test_id=test_id, alias=test_alias, version=test_version, **test_kwargs)

    print "----------------------------------------------"
    print "Test name: ", test
    print "Test type: ", type(test)
    print "----------------------------------------------"

    # Run the test
    score = test.judge(model, deep_error=True)
    print "----------------------------------------------"
    print "Score: ", score
    if "figures" in score.related_data:
        print "Output files: "
        for item in score.related_data["figures"]:
            print item
    print "----------------------------------------------"

    if register_result:
        # Register the result with the HBP Validation service
        model_catalog = ModelCatalog(hbp_username)
        if not hasattr(score.model, 'id') and not model_metadata:
            print "Model = ", model, " => Results NOT saved on validation framework: no model.instance_id or model_metadata provided!"
        elif not hasattr(score.model, 'id'):
            # If model instance_id not specified, register the model on the validation framework
            model_id = model_catalog.register_model(app_id=model_metadata["app_id"],
                                                    name=model_metadata["name"] if "name" in model_metadata else model.name,
                                                    alias=model_metadata["alias"] if "alias" in model_metadata else None,
                                                    author=model_metadata["author"],
                                                    organization=model_metadata["organization"],
                                                    private=model_metadata["private"],
                                                    cell_type=model_metadata["cell_type"],
                                                    model_type=model_metadata["model_type"],
                                                    brain_region=model_metadata["brain_region"],
                                                    species=model_metadata["species"],
                                                    description=model_metadata["description"],
                                                    instances=model_metadata["instances"])
            model_instance_id = model_catalog.get_model_instance(model_id=model_id["uuid"], version=model_metadata["instances"][0]["version"])
            score.model.instance_id = model_instance_id["id"]

        model_instance_json = model_catalog.get_model_instance(instance_id=score.model.instance_id)
        model_json = model_catalog.get_model(model_id=model_instance_json["model_id"])
        model_host_collab_id = model_json["app"]["collab_id"]
        model_name = model_json["name"]

        if not storage_collab_id:
            storage_collab_id = model_host_collab_id
            score.related_data["project"] = storage_collab_id
        #     print "=============================================="
        #     print "Enter Collab ID for Data Storage (if applicable)"
        #     print "(Leave empty for Model's host collab, i.e. ", model_host_collab_id, ")"
        #     score.related_data["project"] = raw_input('Collab ID: ')

        collab_folder = "{}_{}".format(model_name, datetime.now().strftime("%Y%m%d-%H%M%S"))
        collab_storage = CollabDataStore(collab_id=storage_collab_id,
                                         base_folder=collab_folder,
                                         auth=test_library.auth)

        test_library.register_result(test_result=score, data_store=collab_storage)
        # test_library.register_result(test_result=score)