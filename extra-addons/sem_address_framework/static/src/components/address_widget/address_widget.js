/** @odoo-module **/

import { Component, xml, useEffect } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { registry } from "@web/core/registry";
import { Field } from "@web/views/fields/field";

export class SemAddressWidget extends Component {
    static template = "sem_address_framework.SemAddressWidget";
    static components = { Field };
    static props = {
        ...standardFieldProps,
        streetField: { type: String, optional: true },
        street2Field: { type: String, optional: true },
        cityField: { type: String, optional: true },
        zipField: { type: String, optional: true },
        stateField: { type: String, optional: true },
        countryField: { type: String, optional: true },
    };

    setup() {
        this.currentCountryId = this.getM2oId(this.props.record.data[this.props.countryField]);
        this.currentStateId = this.getM2oId(this.props.record.data[this.props.stateField]);

        useEffect(() => {
            const newCountryVal = this.getM2oId(this.props.record.data[this.props.countryField]);
            const newStateVal = this.getM2oId(this.props.record.data[this.props.stateField]);
            let changes = {};

            if (String(newCountryVal) !== String(this.currentCountryId)) {
                this.currentCountryId = newCountryVal;
                if (this.props.stateField) changes[this.props.stateField] = false;
                if (this.props.cityField) changes[this.props.cityField] = false;
                this.currentStateId = false; 
            } else if (String(newStateVal) !== String(this.currentStateId)) {
                this.currentStateId = newStateVal;
                if (this.props.cityField) changes[this.props.cityField] = false;
            }

            if (Object.keys(changes).length > 0) {
                this.props.record.update(changes);
            }
        }, () => [
            this.props.record.data[this.props.countryField],
            this.props.record.data[this.props.stateField]
        ]);
    }

    get record() {
        return this.props.record;
    }

    get stateDomain() {
        if (!this.props.countryField) return [];
        const countryId = this.props.record.data[this.props.countryField];
        const val = this.getM2oId(countryId);
        return val ? [["country_id", "=", val]] : [];
    }

    get cityDomain() {
        if (!this.props.stateField) return [];
        const stateId = this.props.record.data[this.props.stateField];
        const val = this.getM2oId(stateId);
        return val ? [["country_state_id", "=", val]] : [];
    }

    getM2oId(val) {
        if (!val) return false;
        if (Array.isArray(val)) {
            const first = val[0];
            if (typeof first === 'object' && first !== null) {
                return first.id || first.resId || first;
            }
            return first;
        }
        if (typeof val === 'object' && val !== null) {
            return val.id || val.resId || val.res_id || val;
        }
        return val;
    }

}

export const semAddressField = {
    component: SemAddressWidget,
    supportedTypes: ["char", "text"],
    fieldDependencies: (fieldInfo) => {
        const options = fieldInfo.options || {};
        const prefix = options.prefix || "";
        const customKeys = Object.keys(options).filter(k => k !== 'prefix');
        const hasCustomOpts = customKeys.length > 0;
        const deps = [];
        
        const maybeAdd = (optName, defaultName, type) => {
            const customVal = options[optName] || (optName === "city_id" ? options["city"] : false);
            const name = customVal || (prefix ? prefix + defaultName : (hasCustomOpts ? false : defaultName));
            if (name) deps.push({ name, type });
        };

        maybeAdd("street", "street", "char");
        maybeAdd("street2", "street2", "char");
        maybeAdd("city_id", "city_id", "many2one");
        maybeAdd("zip", "zip", "char");
        maybeAdd("state_id", "state_id", "many2one");
        maybeAdd("country_id", "country_id", "many2one");
        
        return deps;
    },
    extractProps: ({ attrs, options }) => {
        const opts = options || {};
        const prefix = opts.prefix || "";
        const customKeys = Object.keys(opts).filter(k => k !== 'prefix');
        const hasCustomOpts = customKeys.length > 0;
        
        const getFieldName = (optName, defaultName) => {
            const customVal = opts[optName] || (optName === "city_id" ? opts["city"] : false);
            return customVal || (prefix ? prefix + defaultName : (hasCustomOpts ? false : defaultName));
        };

        return {
            streetField: getFieldName("street", "street"),
            street2Field: getFieldName("street2", "street2"),
            cityField: getFieldName("city_id", "city_id"),
            zipField: getFieldName("zip", "zip"),
            stateField: getFieldName("state_id", "state_id"),
            countryField: getFieldName("country_id", "country_id"),
        };
    },
};

registry.category("fields").add("sem_address", semAddressField);
