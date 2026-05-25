/** @odoo-module */

import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { rpc } from '@web/core/network/rpc';
import { useService } from '@web/core/utils/hooks';

export class MyProfile extends Component {
    static template = 'SEM.MyProfile';
    static props = { "*": true };

    setup() {
        this.notification = useService('notification');
        this.state = useState({
            profile: null,
            error: null,
            loading: true,
            saving: false,
            activeTab: 'work',
            // editable fields (thông tin cá nhân)
            edit: {},
            // cascade selects
            privateStates: [],
            privateWards: [],
            tempStates: [],
            tempWards: [],
        });

        onWillStart(async () => {
            await this.loadProfile();
        });
    }

    async loadProfile() {
        this.state.loading = true;
        const result = await rpc('/sem/my_profile/data', {});
        if (result.error) {
            this.state.error = result.error;
        } else {
            this.state.profile = result;
            this.state.edit = {
                private_phone: result.private_phone,
                private_email: result.private_email,
                gender: result.gender,
                birthday: result.birthday,
                place_of_birth: result.place_of_birth,
                place_of_origin: result.place_of_origin,
                identification_id: result.identification_id,
                date_issuance_identity_card: result.date_issuance_identity_card,
                local_issuance_identity_card: result.local_issuance_identity_card,
                marital: result.marital,
                children: result.children,
                emergency_contact: result.emergency_contact,
                emergency_phone: result.emergency_phone,
                private_street: result.private_street,
                private_street2: result.private_street2,
                private_state_id: result.private_state_id,
                private_state_name: result.private_state_name,
                private_state_ward_id: result.private_state_ward_id,
                private_state_ward_name: result.private_state_ward_name,
                private_country_id: result.private_country_id,
                private_country_name: result.private_country_name,
                private_zip: result.private_zip,
                temp_street: result.temp_street,
                temp_street2: result.temp_street2,
                temp_state_id: result.temp_state_id,
                temp_state_name: result.temp_state_name,
                temp_state_ward_id: result.temp_state_ward_id,
                temp_state_ward_name: result.temp_state_ward_name,
                temp_country_id: result.temp_country_id,
                temp_country_name: result.temp_country_name,
                temp_zip: result.temp_zip,
            };
            // Load states nếu đã có country
            if (result.private_country_id) {
                this.state.privateStates = await rpc('/sem/my_profile/get_states', { country_id: result.private_country_id });
            }
            if (result.private_state_id) {
                this.state.privateWards = await rpc('/sem/my_profile/get_wards', { state_id: result.private_state_id });
            }
            if (result.temp_country_id) {
                this.state.tempStates = await rpc('/sem/my_profile/get_states', { country_id: result.temp_country_id });
            }
            if (result.temp_state_id) {
                this.state.tempWards = await rpc('/sem/my_profile/get_wards', { state_id: result.temp_state_id });
            }
        }
        this.state.loading = false;
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    onEditChange(field, ev) {
        this.state.edit[field] = ev.target.value || (ev.target.type === 'number' ? 0 : '');
    }

    // ── Cascade: thường trú ──────────────────────────────────────
    async onPrivateStateChange(ev) {
        const stateId = parseInt(ev.target.value) || false;
        const stateName = ev.target.options[ev.target.selectedIndex]?.text || '';
        this.state.edit.private_state_id = stateId;
        this.state.edit.private_state_name = stateName;
        this.state.edit.private_state_ward_id = false;
        this.state.edit.private_state_ward_name = '';
        this.state.privateWards = stateId ? await rpc('/sem/my_profile/get_wards', { state_id: stateId }) : [];
    }

    onPrivateWardChange(ev) {
        this.state.edit.private_state_ward_id = parseInt(ev.target.value) || false;
        this.state.edit.private_state_ward_name = ev.target.options[ev.target.selectedIndex]?.text || '';
    }

    // ── Cascade: tạm trú ─────────────────────────────────────────
    async onTempStateChange(ev) {
        const stateId = parseInt(ev.target.value) || false;
        const stateName = ev.target.options[ev.target.selectedIndex]?.text || '';
        this.state.edit.temp_state_id = stateId;
        this.state.edit.temp_state_name = stateName;
        this.state.edit.temp_state_ward_id = false;
        this.state.edit.temp_state_ward_name = '';
        this.state.tempWards = stateId ? await rpc('/sem/my_profile/get_wards', { state_id: stateId }) : [];
    }

    onTempWardChange(ev) {
        this.state.edit.temp_state_ward_id = parseInt(ev.target.value) || false;
        this.state.edit.temp_state_ward_name = ev.target.options[ev.target.selectedIndex]?.text || '';
    }

    // ── Save ─────────────────────────────────────────────────────
    async save() {
        this.state.saving = true;
        const vals = {
            private_phone: this.state.edit.private_phone,
            private_email: this.state.edit.private_email,
            gender: this.state.edit.gender,
            birthday: this.state.edit.birthday || false,
            place_of_birth: this.state.edit.place_of_birth,
            place_of_origin: this.state.edit.place_of_origin,
            identification_id: this.state.edit.identification_id,
            date_issuance_identity_card: this.state.edit.date_issuance_identity_card || false,
            local_issuance_identity_card: this.state.edit.local_issuance_identity_card,
            marital: this.state.edit.marital,
            children: parseInt(this.state.edit.children) || 0,
            emergency_contact: this.state.edit.emergency_contact,
            emergency_phone: this.state.edit.emergency_phone,
            private_street: this.state.edit.private_street,
            private_street2: this.state.edit.private_street2,
            private_state_id: this.state.edit.private_state_id || false,
            private_state_ward: this.state.edit.private_state_ward_id || false,
            private_country_id: this.state.edit.private_country_id || false,
            private_zip: this.state.edit.private_zip,
            temp_street: this.state.edit.temp_street,
            temp_street2: this.state.edit.temp_street2,
            temp_state_id: this.state.edit.temp_state_id || false,
            temp_state_ward: this.state.edit.temp_state_ward_id || false,
            temp_country_id: this.state.edit.temp_country_id || false,
            temp_zip: this.state.edit.temp_zip,
        };
        const res = await rpc('/sem/my_profile/save', { vals });
        this.state.saving = false;
        if (res.success) {
            this.notification.add('Lưu thành công!', { type: 'success' });
            await this.loadProfile();
        } else {
            this.notification.add(res.error || 'Lưu thất bại', { type: 'danger' });
        }
    }

    // ── Avatar upload ─────────────────────────────────────────────
    triggerAvatarUpload() {
        document.getElementById('sem_avatar_input').click();
    }

    async onAvatarChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('avatar', file);
        const res = await fetch('/sem/my_profile/upload_avatar', {
            method: 'POST',
            body: formData,
        });
        const data = await res.json();
        if (data.success) {
            this.state.profile.image = data.image;
            this.notification.add('Cập nhật ảnh thành công!', { type: 'success' });
        } else {
            this.notification.add(data.error || 'Upload thất bại', { type: 'danger' });
        }
    }
}

registry.category('actions').add('sem_my_profile_action', MyProfile);
