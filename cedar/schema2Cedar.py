import json
import os
import logging
from jinja2 import Template
import datetime
from cedar.utils import set_template_element_property_minimals, set_sub_context, set_context, set_stripped_properties
import cedar.client
import requests

# Set some required variables
configfile_path = os.path.join(os.path.dirname(__file__), "../tests/test_config.json")
if not (os.path.exists(configfile_path)):
    print("Please, create the config file.")
with open(configfile_path) as config_data_file:
    config_json = json.load(config_data_file)
config_data_file.close()
loaded_specs = {}


class Schema2CedarBase:
    """ The base converter class, should not be called ! """

    def __init__(self):
        self.production_api_key = config_json["production_key"]
        self.folder_id = config_json["folder_id"]
        self.user_id = config_json["user_id"]

    def __new__(cls):
        if cls is Schema2CedarBase:
            raise TypeError("base class may not be instantiated")
        return object.__new__(cls)

    @staticmethod
    def json_pretty_dump(json_object, output_file):
        return json.dump(json_object, output_file, sort_keys=False, indent=4, separators=(',', ': '))


class Schema2CedarTemplate(Schema2CedarBase):
    """ Schema 2 Template Converter, this is the one you want to use """

    cedar_template = Template('''
{% set props = ["@context", "@type", "@id" ] %}
{
    "$schema": "http://json-schema.org/draft-04/schema#",
    "@id": null,
    "@context": {{ TEMPLATE_CONTEXT | tojson }},
    "@type": "{{ TEMPLATE_TYPE }}",
    "type": "object",
    "title": "{{ title }} element schema", 
    "description": "{{ description }} ",
    "schema:name": "{{title}}",
    "schema:description": "{{ description }}",
    "schema:schemaVersion": "1.4.0",
    "bibo:status":"bibo:draft",
    "pav:version":"0.1",
    "pav:createdOn": "{{ NOW  }}",
    "pav:lastUpdatedOn": "{{ NOW  }}",
    "pav:createdBy": "{{ USER_URL }}",
    "oslc:modifiedBy": "{{ USER_URL }}",
    "_ui": { 
        "order": [ 
            {% for item in TEMP_PROP %}
                "{{item}}" {% if not loop.last %},{% endif %}      
            {% endfor %} 
        ],
        "propertyLabels": {
            {% for item in TEMP_PROP %}   
                "{{item}}" : "{{item}}"{% if not loop.last %},{% endif %} 
            {% endfor %} 
        },
        "pages": []
    },
    "required": [
        "@context",
        "@id",
        "schema:isBasedOn",
        "schema:name",
        "schema:description",
        "pav:createdOn",
        "pav:createdBy",
        "pav:lastUpdatedOn",
        "oslc:modifiedBy",
        "pav:version",
        "bibo:status"
    ],   
    "additionalProperties": {% if additionalProperties %} {{ additionalProperties }} {% else %} false {% endif%},
    "properties":{
        {% for itemKey, itemVal in PROP_ITEMS.items() %}
            "{{itemKey}}": {{itemVal | tojson}} {% if not loop.last %},{% endif %}
        {% endfor %},
        "@context":{
            "additionalProperties": false,
            "type": "object",
            "properties": {{ PROP_CONTEXT | tojson }},
            "required": [
                "xsd",
                "pav",
                "schema",
                "oslc",
                "schema:isBasedOn",
                "schema:name",
                "schema:description",
                "pav:createdOn",
                "pav:createdBy",
                "pav:lastUpdatedOn",
                "oslc:modifiedBy"
            ]    
        }
        {% if REQ %},{% endif %}
        {% for itemKey, itemVal in REQ.items() %}
            ,"{{itemKey}}": {{itemVal | tojson}}
        {% endfor %}
        {% for itemKey, itemVal in SUB_SPECS.items() %}
            ,"{{itemKey}}": {{itemVal | tojson}}
        {% endfor %}             
    }
}
''')

    def convert_template(self, schema_filename):
        cedar_type = "https://schema.metadatacenter.org/core/Template"

        try:
            with open(schema_filename, 'r') as orig_schema_file:

                input_json_schema = json.load(orig_schema_file)
                orig_schema_file.close()

                # Set the current date
                now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S-0700')

                # Set the user url
                user_url = "https://metadatacenter.org/users/" + config_json["user_id"]

                # Set the sub-specifications from $ref if needed, enabling templateElement nesting
                sub_spec_container = {}
                sub_spec = Schema2CedarTemplateElement().set_sub_specs(input_json_schema['properties'], sub_spec_container)

                cedar_schema = self.cedar_template.render(input_json_schema,
                                                          TEMPLATE_CONTEXT=cedar.utils.set_context(),
                                                          TEMPLATE_TYPE=cedar_type,
                                                          PROP_CONTEXT=cedar.utils.set_prop_context(input_json_schema),
                                                          NOW=now,
                                                          REQ=cedar.utils.set_required_item(input_json_schema),
                                                          PROP_ITEMS=cedar.utils.set_properties_base_item(),
                                                          USER_URL=user_url,
                                                          TEMP_PROP=cedar.utils.set_stripped_properties(input_json_schema),
                                                          SUB_SPECS=sub_spec)

                return cedar_schema

        except IOError:
            logging.error("Error opening schema file")


class Schema2CedarTemplateElement(Schema2CedarBase):
    """Schema to TemplateElement converter, should not be called directly"""

    cedar_template_element = Template('''
    {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "@id": null,
        "@context": {{TEMPLATE_CONTEXT | tojson}},
        "@type": "{{TEMPLATE_TYPE}}",
        "type": "object",
        "title": "{{title}} element schema", 
        "description": "{{description}} ",
        "schema:name": "{{FIELD_KEY}}",
        "schema:description": "{{description}}",
        "schema:schemaVersion": "1.4.0",
        "bibo:status":"bibo:draft",
        "pav:version":"0.1",
        "pav:createdOn": "{{NOW}}",
        "pav:lastUpdatedOn": "{{NOW}}",
        "pav:createdBy": "{{USER_URL}}",
        "oslc:modifiedBy": "{{USER_URL}}",
        "_ui": { 
            "order": [ 
                {% for item in TEMP_PROP %}
                    "{{item}}" {% if not loop.last %},{% endif %}      
                {% endfor %} 
            ],
            "propertyLabels": {
                {% for item in TEMP_PROP %}   
                    "{{item}}" : "{{item}}"{% if not loop.last %},{% endif %} 
                {% endfor %}
            }
        },
        {% set requiredList = required %}
        "required":[
            "@context",
            "@id"
            {% for item in requiredList %}
                ,"{{item}}"
            {% endfor %}
        ],
        "properties": {
            {% for itemKey, itemVal in PROP_CONTEXT.items() %}    
                "{{itemKey}}": {{itemVal | tojson}} {% if not loop.last %},{% endif %}
            {% endfor %},
            {% for itemKey, itemVal in TEMP_PROP.items() %}
                {% if '$ref' in itemVal %}
                    {% if itemKey in SUB_SPECS %} "{{itemKey}}": {{SUB_SPECS[itemKey] | tojson}}                     
                    {% endif %}
                {% elif 'items' in itemVal and '$ref' in itemVal['items'] %}
                    {% if itemKey in SUB_SPECS %} "{{itemKey}}": {{SUB_SPECS[itemKey] | tojson}}                     
                    {% endif %}    
                {% else %}               
                    "{{itemKey}}": {
                        "@context": {{ITEM_CONTEXT | tojson}},
                        "title": "{{itemKey}} field schema generated by {{MIRCAT}}",
                        "schema:description": "{{itemKey}}",  
                        "additionalProperties": false,
                        "oslc:modifiedBy": "{{USER_URL}}",
                        "pav:createdOn": "{{NOW}}",
                        "_ui": {
                            "inputType": "textfield"
                        },
                        "description": 
                            {% if itemVal.description %} "{{itemVal.description}}" 
                            {%else %} "{{item}} autogenerated by {{MIRCAT}}" 
                            {% endif %},
                        "pav:lastUpdatedOn": "{{NOW}}",
                        "required": [
                            "@value"
                        ],
                        "@type": "https://schema.metadatacenter.org/core/TemplateField",
                        "_valueConstraints": {
                            {% if itemVal['_valueConstraints'] is defined and itemVal['_valueConstraints']['defaultValue'] is defined %}
                                "defaultValue": "{{itemVal['_valueConstraints']['defaultValue']}}",
                            {% endif %}
                            "requiredValue":
                                {% if (requiredList is defined) and (itemKey in requiredList) %} true 
                                {% else %} false 
                                {% endif%}
                        },
                        "pav:createdBy": "{{USER_URL}}",
                        "schema:name": "{{itemKey}}",
                        "@id": null,
                        "schema:schemaVersion": "1.4.0",
                        "type": "object",
                        "$schema": "http://json-schema.org/draft-04/schema#",
                        "properties": {
                            "@type": {
                                "oneOf": [
                                    {
                                      "format": "uri",
                                      "type": "string"
                                    },
                                    {
                                        "uniqueItems": true,
                                        "minItems": 1,
                                        "type": "array",
                                        "items": {
                                            "format": "uri",
                                            "type": "string"
                                        }
                                    }
                                ]
                            },
                            "@value": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            },
                            "rdfs:label": {
                                "type": [
                                    "string",
                                    "null"
                                ]
                            }
                        }
                    }
                {% endif %}                                                               
                {% if not loop.last %},{% endif %}
            {% endfor %}
        },
         "additionalProperties": {% if additionalProperties %} {{additionalProperties}} {% else %} false {% endif%}
    }
    ''')

    def convert_template_element(self, schema_file_path, **kwargs):
        cedar_type = "https://schema.metadatacenter.org/core/TemplateElement"

        try:
            with open(schema_file_path, 'r') as orig_schema_file:

                # Load the JSON schema and close the file
                schema_as_json = json.load(orig_schema_file)
                orig_schema_file.close()

                # Set the current date
                now = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S-0700')

                # Set the user url
                user_url = "https://metadatacenter.org/users/" + config_json["user_id"]

                # Set root['@context']
                context = set_context()

                # Set root['properties']['@context']
                property_context = set_template_element_property_minimals(set_sub_context(schema_as_json),
                                                                          schema_as_json['properties'])

                # Set root['properties']['item_name']['@context']
                item_context = dict(context)
                item_context.pop("bibo")

                # Set the sub-specifications from $ref if needed, enabling templateElement nesting
                sub_spec_container = {}
                sub_spec = self.set_sub_specs(schema_as_json['properties'], sub_spec_container)

                # Get the optional parameter for schema:name (useful when nesting)
                field_key = kwargs.get('fieldKey', None)
                if field_key is None:
                    field_key = schema_as_json['title']

                # Return the Jinja2 template
                return self.cedar_template_element.render(schema_as_json,
                                                     TEMPLATE_TYPE=cedar_type,
                                                     TEMPLATE_CONTEXT=context,
                                                     NOW=now,
                                                     USER_URL=user_url,
                                                     MIRCAT="mircat-tools for python 3",
                                                     PROP_CONTEXT=property_context,
                                                     ITEM_CONTEXT=item_context,
                                                     TEMP_PROP=set_stripped_properties(schema_as_json),
                                                     SUB_SPECS=sub_spec,
                                                     FIELD_KEY=field_key)

        except IOError:
            logging.error("Error opening schema file")

    def set_sub_specs(self, schema, sub_spec_container):
        ignored_key = ["@id", "@type", "@context"]
        data_dir = os.path.join(os.path.dirname(__file__), "../tests/data")
        client = cedar.client.CEDARClient()
        headers = client.get_headers(self.production_api_key)
        request_url = client.selectEndpoint('production') \
                      + "/template-elements?folder_id=https%3A%2F%2Frepo.metadatacenter.org%2Ffolders%2F" \
                      + self.folder_id

        # For each field in the properties array
        for itemKey, itemVal in schema.items():

            # if the field is not to be ignored
            if itemKey not in ignored_key:

                # set the schema_path to load to None
                schema_path = None
                multiple_items = False

                if '$ref' in itemVal:
                    schema_path = os.path.join(data_dir, itemVal['$ref']
                                               .replace('#', '')) \
                        .replace("http://fairsharing.github.io/MIRcat/miaca/", "")  # build the file path

                elif 'items' in itemVal and '$ref' in itemVal['items']:
                    schema_path = os.path.join(data_dir,
                                               itemVal['items']['$ref'][0].replace('#', ''))  # build the file path
                    multiple_items = True

                elif ('items' in itemVal and ('anyOf' in itemVal['items'] or 'oneOf' in itemVal['items'])) \
                        or ('anyOf' in itemVal) \
                        or ('oneOf' in itemVal):

                    # REFINING HERE -> DELETE ALL ITEMS FROM SERVER !! (or change algo to validate all templates first.
                    raise ValueError("'anyOf' and 'oneOf' are not supported by CEDAR (schema affected: )")

                # if the schema_path is set
                if schema_path is not None:

                    if itemKey not in loaded_specs.keys():
                        temp_spec = json.loads(self.convert_template_element(schema_path, fieldKey=itemKey))

                        # NEED SOME REFINING HERE -> VALIDATE BEFORE POST !!!
                        response = requests.request("POST",
                                                    request_url,
                                                    headers=headers,
                                                    data=json.dumps(temp_spec),
                                                    verify=True)
                        temp_spec["@id"] = json.loads(response.text)["@id"]
                        if multiple_items:
                            sub_spec = {'items': temp_spec, "type": "array", "minItems": 1}
                        else:
                            sub_spec = temp_spec

                        loaded_specs[itemKey] = sub_spec

                    else:
                        sub_spec = loaded_specs[itemKey]

                    sub_spec_container[itemKey] = sub_spec

        return sub_spec_container
