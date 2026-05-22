# Dune Dashboard — Complete Capabilities Reference

> **Generated:** 2026-05-22
> **Purpose:** Comprehensive reference of all dashboard features, database functions, and admin tools
> **⚠️ SECURITY:** This document contains sensitive operational information. Do not commit to GitHub.

---

## Table of Contents

1. [Dashboard Admin Features](#1-dashboard-admin-features)
2. [Database Functions Catalog](#2-database-functions-catalog)
3. [RabbitMQ Exchanges & Queues](#3-rabbitmq-exchanges--queues)
4. [BGD Director API Endpoints](#4-bgd-director-api-endpoints)
5. [Kubernetes Resources](#5-kubernetes-resources)
6. [Game Tables Reference](#6-game-tables-reference)

---

## 1. Dashboard Admin Features

### 1.1 Player Management

| Feature | Purpose | API Endpoint | DB Function / Query |
|---------|---------|--------------|---------------------|
| **Search Players** | Find players by character name or FLS ID | `POST /api/admin-experimental/search-players` | Query on `encrypted_accounts` + `player_state` |
| **Online Players** | List currently online players | `GET /api/admin-experimental/online-players` | `get_all_online_or_recently_disconnected_player_online_state()` |
| **Teleport Player** | Move offline player to partition + coordinates | `POST /api/admin-experimental/teleport` | `admin_move_offline_player_to_partition(fls_id, partition_id, vector)` |
| **Change Faction** | Switch player's faction allegiance | `POST /api/admin-experimental/change-faction` | Direct SQL on `player_faction` table |
| **Faction Reputation** | View/set reputation with factions | `POST /api/admin-experimental/faction-reputation` | `get_player_current_faction_reputation()`, `set_player_faction_reputation()` |
| **Adjust Currency** | Add/remove Solari, House Script, Spice | `POST /api/admin-experimental/adjust-currency` | Direct INSERT/UPDATE on `player_virtual_currency_balances` |
| **View Currency** | Check player's currency balances | `POST /api/admin-experimental/currency-balances` | Query `player_virtual_currency_balances` |
| **Player Tags** | Add/remove metadata tags on accounts | `POST /api/admin-experimental/player-tags` | `admin_read_player_tags()`, `update_player_tags()` |
| **Flag Cheater** | Mark account for cheating | `POST /api/admin-experimental/flag-cheater` | `flag_player_as_cheater(account_id, cheat_type_enum)` |
| **Player Stats** | View health, hydration, spice exposure | `POST /api/admin-experimental/player-stats` | Query `actors.properties` JSONB |
| **Player Vehicles** | List owned vehicles | `POST /api/admin-experimental/player-vehicles` | `get_player_owned_vehicles_data()` |
| **Inventory Lookup** | View player inventory items | `POST /api/admin-experimental/inventory` | `admin_get_inventory_details()` |
| **Set Character Name** | Rename a character | `POST /api/admin-experimental/set-character-name` | `set_character_name(account_id, name)` |
| **Delete Character** | Remove character from account | `POST /api/admin-experimental/delete-character` | `delete_character(actor_id)` |
| **Delete Account** | Full account deletion | `POST /api/admin-experimental/delete-account` | `delete_account(user_id, reason)` |
| **Set Demo State** | Force demo mode state | `POST /api/admin-experimental/set-demo-state` | `set_demo_state(user_id, demo_state_enum)` |

### 1.2 Guild Management

| Feature | Purpose | API Endpoint | DB Function |
|---------|---------|--------------|-------------|
| **List Guilds** | Show all guilds on server | `GET /api/admin-experimental/guilds` | Query `guilds` table |
| **View Guild** | Get guild details + members | `POST /api/admin-experimental/guild-data` | `get_guild_data(guild_id)` |
| **Disband Guild** | Delete guild entirely | `POST /api/admin-experimental/disband-guild` | `disband_guild(guild_id)` |
| **Kick Member** | Remove player from guild | `POST /api/admin-experimental/remove-guild-member` | `remove_guild_members([player_id], guild_id, reason)` |
| **Guild Members** | List guild roster | `POST /api/admin-experimental/guild-members` | `get_guild_members(guild_id)` |
| **Promote Member** | Change guild role | `POST /api/admin-experimental/promote-guild-member` | `promote_guild_member(guild_id, player_id, role_id)` |
| **Demote Member** | Lower guild role | `POST /api/admin-experimental/demote-guild-member` | `demote_guild_member(guild_id, player_id, role_id)` |

### 1.3 Journey & Progression

| Feature | Purpose | API Endpoint | DB Function |
|---------|---------|--------------|-------------|
| **Complete Story Nodes** | Mark journey nodes complete | `POST /api/admin-experimental/journey` (action=complete) | `complete_journey_story_nodes_for_player(player_id, [node_ids])` |
| **Reveal Story Nodes** | Unlock hidden nodes | `POST /api/admin-experimental/journey` (action=reveal) | `reveal_journey_story_nodes_for_player(player_id, [node_ids])` |
| **Reset Story Nodes** | Reset progression | `POST /api/admin-experimental/journey` (action=reset) | `delete_journey_story_nodes_for_player(player_id, [node_ids])` |
| **Set Specialization** | Set XP/level for track | `POST /api/admin-experimental/specialization` | `set_specialization_xp_and_level(player_id, track_type, xp, level)` |
| **Reset Specialization** | Clear spec progress | `POST /api/admin-experimental/reset-specialization` | `reset_specialization_tracks(player_id)` |
| **View Inventory** | See player items | `POST /api/admin-experimental/inventory` | `admin_get_inventory_details(account_id)` |

### 1.4 Economy & World

| Feature | Purpose | API Endpoint | DB Function |
|---------|---------|--------------|-------------|
| **Reset Vendor Stock** | Refresh vendor inventory | `POST /api/admin-experimental/clean-vendor-stock` | `clean_stock_for_player(player_id)` |
| **View Tax Invoices** | Check player tax bills | `POST /api/admin-experimental/tax-invoices` | `taxation_get_all_invoices_for_player(player_id)` |
| **Reset Spice Fields** | Reset spice state on map | `POST /api/admin-experimental/spice` | `reset_global_spice_field_state(map, dim)` |
| **Force Spice Spawn** | Trigger spice field spawn | `POST /api/admin-experimental/spice` | `try_spawn_spicefield(server_id, spicefield_id)` |
| **List Partitions** | Show all world partitions | `GET /api/admin-experimental/partitions` | Query `world_partition` table |
| **Battlegroup Info** | Full server status | `GET /api/admin-experimental/battlegroup` | BGD API `/v0/battlegroup` |

### 1.5 Server Administration

| Feature | Purpose | API Endpoint | DB Function |
|---------|---------|--------------|-------------|
| **Set Players Offline** | Force all players offline | `POST /api/admin-experimental/server-tools` | `set_players_from_server_ids_offline([server_ids])` |
| **Cleanup Orphans** | Remove orphaned entities | `POST /api/admin-experimental/server-tools` | `cleanup_orphaned_entities()` |
| **View Permissions** | Check actor permissions | `POST /api/admin-experimental/permissions` | `get_permission_for_actors([actor_ids])` |
| **Set Player Rank** | Set permission rank | `POST /api/admin-experimental/permissions` | `permission_set_player_rank(actor_id, player_id, rank, map_id)` |
| **In-Game Broadcast** | Send notification to all players | `POST /api/admin-experimental/broadcast` | `rabbitmqctl eval` on RMQ pod (Erlang) |
| **Ban Player** | Ban with duration | `POST /api/ban_player` | Insert into `dashboard.bans` + iptables |
| **Unban Player** | Remove ban | `POST /api/unban_player` | Delete from `dashboard.bans` + iptables |
| **Kick Player** | Temporary kick | `POST /api/kick_player` | iptables DROP for 60 seconds |
| **Detect Player IPs** | Parse logs for IPs | `POST /api/detect_player_ips` | SSH + kubectl to read game logs |

### 1.6 Item & Entity Editing

| Feature | Purpose | API Endpoint | DB Function |
|---------|---------|--------------|-------------|
| **Edit Item** | Modify stack size, quality, durability | `POST /api/edit_item` | Direct UPDATE on `items` table |
| **Delete Item** | Remove item | `POST /api/delete_item` | `DELETE FROM items WHERE id = ?` |
| **Add Item** | Spawn item to inventory | `POST /api/add_item` | `INSERT INTO items ...` |
| **Edit Vitals** | Change health, hydration, spice | `POST /api/edit_vitals` | UPDATE `actors.properties` + `gas_attributes` |
| **Edit Tech Knowledge** | Set tech points | `POST /api/edit_tech_knowledge` | UPDATE `actors.properties` (TechKnowledgePlayerComponent) |
| **Edit XP** | Set specialization XP | `POST /api/edit_xp` | UPSERT on `specialization_tracks` |
| **Edit Faction** | Change faction directly | `POST /api/edit_faction` | UPSERT on `player_faction` |
| **Edit Currency** | Set exact balance | `POST /api/edit_currency` | UPSERT on `player_virtual_currency_balances` |

### 1.7 Function Explorer

| Feature | Purpose | API Endpoint |
|---------|---------|--------------|
| **List Functions** | Get all 517 DB functions | `GET /api/admin-experimental/functions` |
| **Get Function** | View function definition | `GET /api/admin-experimental/functions/:name` |
| **Execute Function** | Call function with params | `POST /api/admin-experimental/functions/:name/execute` |
| **Execute SQL** | Run raw SQL (admin only) | `POST /api/admin-experimental/execute` |

### 1.8 File Browser

| Feature | Purpose | API Endpoint |
|---------|---------|--------------|
| **List Files** | Browse `/srv` directory | `POST /api/files/list` |
| **View File** | Read file content | `GET /api/files/view` |
| **Save File** | Edit file content | `POST /api/files/save` |

---

## 2. Database Functions Catalog

### 2.1 Admin & Debug Functions (24 functions)

| Function | Purpose |
|----------|---------|
| `admin_get_character_details(in_account_id bigint)` | Get full character data for account |
| `admin_get_character_ids(in_search_term text)` | Search characters by name pattern |
| `admin_get_inventory_details(in_account_id bigint)` | Get all inventory items for account |
| `admin_get_journey_details(in_player_id text, in_story_node_id text)` | Get journey node progress |
| `admin_get_mnemonic_recall_details(in_account_id bigint)` | Get mnemonic recall lessons |
| `admin_get_partitions()` | List all world partitions |
| `admin_move_offline_player(in_fls_id text, in_target_partition_name text, in_target_location vector)` | Teleport by partition name |
| `admin_move_offline_player_to_partition(in_fls_id text, in_target_partition_id bigint, in_target_location vector)` | Teleport by partition ID |
| `admin_read_player_tags(in_account_id bigint)` | Get tags for account |
| `debug_add_test_table_data(in_entry text)` | Debug: insert test data |
| `debug_collect_test_table_data()` | Debug: collect test data |
| `debug_echo(in_text text, in_notices text[])` | Debug: echo with notices |
| `debug_get_coriolis_seeds()` | Debug: get all Coriolis seeds |
| `debug_raise_exception(in_exception text, in_notices text[])` | Debug: raise exception |
| `debug_raise_notices(in_notices text[])` | Debug: raise notices |
| `debug_reset_test_table()` | Debug: reset test table |
| `debug_set_farm_seed(in_new_coriolis_seed integer)` | Debug: set farm seed |
| `debug_set_map_seed(in_map text, in_new_coriolis_seed integer)` | Debug: set map seed |
| `debug_set_partition_seed(in_partition_id bigint, in_new_coriolis_seed integer)` | Debug: set partition seed |
| `get_all_demo_players()` | Get all demo state players |
| `get_all_faction_members()` | Get all faction members |
| `get_all_guild_members()` | Get all guild members |
| `get_all_online_or_recently_disconnected_player_online_state()` | Get online players |
| `get_schema_version()` | Get DB schema version |

### 2.2 Character Transfer Functions (22 functions)

| Function | Purpose |
|----------|---------|
| `_character_transfer_allocate_id(kind dune._charactertransferentrykind, data jsonb)` | Allocate transfer ID |
| `_character_transfer_create_data_table()` | Create transfer data table |
| `_character_transfer_data_filter(id text, removed text[], VARIADIC refs dune._charactertransferdatafilterref[])` | Filter transfer data |
| `_character_transfer_data_table_load(entries jsonb)` | Load transfer data table |
| `_character_transfer_data_table_save()` | Save transfer data table |
| `_character_transfer_ensure_player_is_owner_of_vbt_vehicle(in_vehicle_id bigint[])` | Validate vehicle ownership |
| `_character_transfer_get_filter(kind dune._charactertransferentrykind)` | Get transfer filter |
| `_character_transfer_get_patches_checksum()` | Get patches checksum |
| `_character_transfer_pre_export_validation(in_fls_id text)` | Pre-export validation |
| `_character_transfer_property_not_exported_is_expected(path text)` | Check property export |
| `_character_transfer_replace_local_id_with_transfer_id(data text, path text)` | Replace IDs for export |
| `_character_transfer_replace_local_id_with_transfer_id_in_json(data jsonb, path text)` | Replace IDs in JSON |
| `_character_transfer_replace_transfer_id_with_local_id(data text, path text)` | Replace IDs for import |
| `_character_transfer_replace_transfer_id_with_local_id_in_json(data jsonb, path text)` | Replace IDs in JSON |
| `_character_transfer_store_in_world_owned_vehicles_into_recovery(in_player_id bigint)` | Store vehicles in recovery |
| `_character_transfer_top_level_export(in_kind dune._charactertransferentrykind, data jsonb)` | Export character data |
| `_character_transfer_top_level_import(in_kind dune._charactertransferentrykind, data jsonb, in_id bigint)` | Import character data |
| `character_migration_export(in_fls_id text)` | Export for migration |
| `character_migration_import(in_data jsonb, in_fls_id text, in_character_name text)` | Import migration data |
| `character_transfer_export(in_fls_id text)` | Export character |
| `character_transfer_get_unsaved_counts(in_fls_id text)` | Get unsaved counts |
| `character_transfer_import(in_data jsonb, in_fls_id text, in_character_name text)` | Import character |

### 2.3 Guild & Faction Functions (28 functions)

| Function | Purpose |
|----------|---------|
| `accept_guild_invite(in_invite_id bigint, in_role_id smallint, ...)` | Accept guild invite |
| `add_guild_invite(in_player_id bigint, in_guild_id bigint, ...)` | Create guild invite |
| `add_guild_member(in_player_id bigint, in_guild_id bigint, ...)` | Add member to guild |
| `break_guild_allegiance(in_guild_id bigint, in_neutral_faction_id smallint)` | Break guild allegiance |
| `change_player_faction(in_player_id bigint, in_faction_id smallint, ...)` | Change player faction |
| `clean_guild_invites_with_incompatible_faction(in_player_id bigint, in_faction_id smallint, ...)` | Clean incompatible invites |
| `clean_old_guild_invites(in_cutoff_timespan bigint)` | Clean old guild invites |
| `create_guild(in_player_id bigint, in_neutral_faction smallint, ...)` | Create new guild |
| `demote_guild_member(in_guild_id bigint, in_player_id bigint, in_new_role smallint)` | Demote guild member |
| `disband_guild(in_guild_id bigint)` | Disband guild |
| `get_guild_data(in_guild_id bigint)` | Get guild details |
| `get_guild_data_for_player(in_player_id bigint)` | Get guild for player |
| `get_guild_for_player(in_player_id bigint)` | Get guild ID for player |
| `get_guild_invites(in_guild_id bigint)` | Get guild invites |
| `get_guild_members(in_guild_id bigint)` | Get guild member list |
| `guild_handle_actor_delete(in_player_id bigint)` | Handle actor delete |
| `guilds_get_exclusive_operation_lock()` | Get guild operation lock |
| `handle_player_faction_guild_effects(in_player_id bigint, in_faction_id smallint, ...)` | Apply faction effects |
| `is_player_guild_admin(in_player_id bigint, in_guild_id bigint)` | Check if guild admin |
| `pledge_guild_allegiance(in_guild_id bigint, in_guild_leader_player_id bigint, ...)` | Pledge allegiance |
| `promote_guild_member(in_guild_id bigint, in_player_id bigint, in_new_role smallint)` | Promote guild member |
| `remove_guild_members(in_player_ids bigint[], in_guild_id bigint, in_remove_reason smallint)` | Remove members |
| `get_player_current_faction_reputation(in_actor_id bigint)` | Get faction reputation |
| `get_player_faction(in_player_id bigint, in_neutral_faction_id smallint)` | Get player faction |
| `get_player_faction_name(in_actor_id bigint)` | Get faction name |
| `set_player_faction_reputation(in_actor_id bigint, in_faction_id smallint, in_reputation_amount integer)` | Set reputation |
| `get_all_player_in_guild_online_state(in_guild_id bigint)` | Get guild online members |
| `get_player_ids_online_state(in_player_ids bigint[])` | Get player online status |

### 2.4 Party Functions (13 functions)

| Function | Purpose |
|----------|---------|
| `accept_party_invite(in_invite_id bigint, in_platform_session_id text, in_max_party_member_count integer)` | Accept party invite |
| `add_party_invite(in_sender_player_id bigint, in_sender_platform_name text, ...)` | Create party invite |
| `clean_expired_party_invites(in_invite_expire_seconds integer)` | Clean expired invites |
| `disband_party(in_party_id bigint)` | Disband party |
| `get_all_parties()` | Get all parties |
| `get_all_party_invites()` | Get all party invites |
| `get_all_party_members()` | Get all party members |
| `get_party_members(in_party_id bigint)` | Get party members |
| `internal_add_party_member(in_invite_id bigint, in_party_id bigint, ...)` | Add party member |
| `internal_create_party(in_invite_id bigint, in_leader_id bigint, ...)` | Create party |
| `join_platform_session_party(in_leader_platform_id text, in_player_platform_id text, ...)` | Join platform party |
| `parties_get_exclusive_operation_lock()` | Get party operation lock |
| `promote_new_party_leader(in_party_id bigint)` | Promote new leader |
| `promote_party_leader_to(in_party_id bigint, in_player_id bigint)` | Set party leader |
| `remove_party_invite(in_invite_id bigint, in_remove_reason smallint)` | Remove party invite |
| `remove_party_member(in_player_id bigint, in_remove_reason smallint)` | Remove party member |
| `update_party_platform_session(in_party_id bigint, in_platform_session_id text, in_platform_name text)` | Update platform session |

### 2.5 Inventory & Items (42 functions)

| Function | Purpose |
|----------|---------|
| `add_item_delete_log(in_item_id bigint, in_inventory_id bigint, in_template_id text)` | Log item delete |
| `add_item_trace_log(...)` | Log item movement |
| `advance_items_id_sequencer(count bigint)` | Advance item ID sequence |
| `delete_inventory_item(in_item_id bigint, in_count bigint)` | Delete inventory item |
| `get_inventory_data(in_inventory_id bigint)` | Get inventory data |
| `get_inventory_id(in_actor_id bigint, in_component_name_hash integer)` | Get inventory ID |
| `get_items_to_remove(items_to_remove text[])` | Get items to remove |
| `get_sub_inventory_id(in_owner_item_id bigint)` | Get sub-inventory ID |
| `load_items(in_inventory_id bigint)` | Load inventory items |
| `merge_inventory_items(in_item_id bigint, in_dst_inventory_id bigint, ...)` | Merge item stacks |
| `merge_or_move_inventory_item(in_item_id bigint, in_dst_inventory_id bigint, ...)` | Merge or move item |
| `move_inventory_item(in_item_id bigint, in_dst_inventory_id bigint, ...)` | Move item |
| `save_item(in_item dune.inventoryitem)` | Save item |
| `update_inventories_data(in_inventory_data_list dune.inventorydata[])` | Update inventories |
| `update_inventory(in_delete_list bigint[], in_stack_update dune.itemstackupdate[], ...)` | Update inventory |
| `update_item_locations(in_item_locations dune.inventoryitemlocation[])` | Update item locations |
| `admin_get_inventory_details(in_account_id bigint)` | Get inventory for account |
| `get_exchange_inventory_id(in_exchange_id bigint)` | Get exchange inventory |
| `get_vehicle_module_inventory_id(in_vehicle_module_id bigint, in_vehicle_module_inventory_type integer)` | Get module inventory |
| `load_building(in_building_id bigint)` | Load building data |
| `load_placeable(in_placeable_id bigint)` | Load placeable data |
| `load_totem(in_id bigint)` | Load totem data |
| `load_vehicle_modules(in_vehicle_id bigint)` | Load vehicle modules |
| `save_building(in_building_id bigint, in_data dune.buildingsavedata)` | Save building |
| `save_placeable(in_placeable_id bigint, in_data dune.placeablesavedata)` | Save placeable |
| `save_totem(in_id bigint, in_data dune.totemsavedata)` | Save totem |
| `save_vehicle_modules(in_add_list dune.vehiclemodule[], in_delete_list bigint[], ...)` | Save vehicle modules |
| `base_backup_delete(in_base_backup_id bigint)` | Delete base backup |
| `base_backup_find_totems_from_player_owner(in_player_id bigint)` | Find totems for backup |
| `base_backup_finish_placing(in_base_backup_id bigint)` | Finish placing backup |
| `base_backup_get_actors_to_spawn(in_base_backup_id bigint)` | Get actors to spawn |
| `base_backup_get_available_backups(in_player_id bigint)` | Get available backups |
| `base_backup_get_buildable_data(in_base_backup_id bigint)` | Get buildable data |
| `base_backup_get_data(in_base_backup_id bigint)` | Get backup data |
| `base_backup_get_totem_data(in_base_backup_id bigint)` | Get totem data |
| `base_backup_get_totem_data_from_totem_id(in_totem_id bigint)` | Get totem data by ID |
| `base_backup_get_totem_id(backup_id bigint)` | Get totem ID |
| `base_backup_recycle(in_base_backup_id bigint, in_target_inventory_id bigint)` | Recycle backup |
| `base_backup_save(in_player_actor_id bigint, in_base_backup_name text, ...)` | Save base backup |
| `base_backup_save_all_totems_from_player_owner(in_player_id bigint)` | Save all totems |
| `base_backup_save_from_totem(in_player_id bigint, totem_id bigint)` | Save from totem |
| `get_unbacked_up_vehicle_ids_for_account(in_account_id bigint)` | Get unbacked vehicles |

### 2.6 Currency & Economy (21 functions)

| Function | Purpose |
|----------|---------|
| `adjust_player_virtual_currency_balance(in_controller_id bigint, in_currency_id smallint, in_delta bigint)` | Adjust currency |
| `dune_exchange_add_sell_order(...)` | Add exchange sell order |
| `dune_exchange_cancel_order(in_order_id bigint, in_purge_time bigint, in_completion_type integer)` | Cancel order |
| `dune_exchange_expire_orders(in_exchange_id bigint, in_current_time bigint, ...)` | Expire orders |
| `dune_exchange_fulfill_sell_order(...)` | Fulfill sell order |
| `dune_exchange_get_item_price_stats(in_template_ids text[])` | Get price stats |
| `dune_exchange_get_user_id(in_owner_id bigint)` | Get exchange user ID |
| `dune_exchange_get_used_order_slots(in_controller_id bigint)` | Get used slots |
| `dune_exchange_modify_user_solari_balance(in_controller_id bigint, in_solari_delta bigint)` | Modify Solari |
| `dune_exchange_purge_completed_orders(in_exchange_id bigint, in_current_time bigint)` | Purge completed |
| `dune_exchange_query_storage_item(in_order_id bigint)` | Query storage item |
| `dune_exchange_query_storage_items(in_exchange_id bigint, in_owner_id bigint)` | Query storage items |
| `dune_exchange_relist_order(in_order_id bigint, in_expiration_time bigint, ...)` | Relist order |
| `dune_exchange_retrieve_solari_balance(in_owner_id bigint)` | Retrieve Solari |
| `dune_exchange_retrieve_solaris_from_item(in_controller_id bigint, in_order_id bigint)` | Retrieve from item |
| `dune_exchange_retrieve_storage_item(in_exchange_id bigint, in_order_id bigint, ...)` | Retrieve storage item |
| `dune_exchange_update_recurring_sell_order(...)` | Update recurring order |
| `get_dune_exchange_accesspoint_id(in_exchange_id bigint, in_name text)` | Get access point |
| `get_dune_exchange_data(in_exchange_id bigint, in_controller_id bigint)` | Get exchange data |
| `get_dune_exchange_id(in_name text)` | Get exchange ID |
| `get_player_virtual_currency_balances(in_controller_id bigint)` | Get currency balances |
| `get_solaris_id()` | Get Solari currency ID |
| `taxation_emit_invoices(new_tax_invoices dune.taxinvoicedata[])` | Emit tax invoices |
| `taxation_get_all_invoices_for_player(in_player_id bigint)` | Get player invoices |
| `taxation_get_all_invoices_for_server(map_name text, in_dimension_index integer, in_partition_id bigint)` | Get server invoices |
| `taxation_get_all_invoices_for_totem(in_totem_id bigint)` | Get totem invoices |
| `taxation_pay_invoice(invoice_id bigint, paid_invoice_status smallint)` | Pay invoice |
| `taxation_remove_invoices(invoices_to_remove bigint[])` | Remove invoices |
| `taxation_remove_invoices_from_totem(totem_actor_id bigint)` | Remove totem invoices |
| `taxation_update_invoice_status(...)` | Update invoice status |

### 2.7 Journey & Progression (26 functions)

| Function | Purpose |
|----------|---------|
| `complete_journey_nodes_where_prerequisite_nodes_are_complete(story_ids_to_complete text[], prerequisite_completed_story_ids text[])` | Complete nodes |
| `complete_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])` | Complete for player |
| `create_or_update_tutorial_entry(in_player_id bigint, in_tutorial_id smallint, in_tutorial_state smallint)` | Create tutorial |
| `delete_all_journey_story_nodes(in_account_id bigint)` | Delete all nodes |
| `delete_all_tutorial_entries(in_player_id bigint)` | Delete tutorials |
| `delete_journey_story_ids(story_ids text[])` | Delete story IDs |
| `delete_journey_story_node(in_account_id bigint, in_story_node_id text)` | Delete node |
| `delete_journey_story_nodes_for_group_for_player(in_account_id bigint, in_reset_group dune.journeystoryresetgroup)` | Delete group |
| `delete_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])` | Delete for player |
| `delete_journey_story_nodes_for_player_account(in_account_id bigint, in_story_node_ids text[])` | Delete for account |
| `get_all_tutorial_entries(in_player_id bigint)` | Get tutorials |
| `get_login_journey_nodes(in_account_id bigint)` | Get login nodes |
| `get_login_journey_nodes_cooldown(in_account_id bigint)` | Get cooldown |
| `journey_story_node_cooldown_add(in_account_id bigint, in_story_node_id text, in_time_to_expire timestamp)` | Add cooldown |
| `journey_story_node_cooldown_delete_expired(in_time_to_check timestamp)` | Delete expired |
| `load_actors(in_actor_ids bigint[], in_actor_state dune.actorstate)` | Load actors |
| `reset_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])` | Reset nodes |
| `reveal_journey_story_nodes_for_player(in_player_id text, in_story_node_ids text[])` | Reveal nodes |
| `save_journey_story_node(in_account_id bigint, in_story_node_id text, ...)` | Save node |
| `save_journey_story_nodes(in_account_id bigint, in_journey_data dune.savejourneydata[])` | Save nodes |
| `update_journey_story_ids(old_story_ids text[], new_story_ids text[])` | Update IDs |
| `get_character_import_state(in_fls_id text)` | Get import state |
| `get_unresolved_character_imports()` | Get unresolved imports |
| `set_character_import_state(in_fls_id text, in_state dune.transferimportstate)` | Set import state |
| `remove_character_transfer_state(in_fls_id text)` | Remove transfer state |
| `get_character_transfer_related_items(in_fls_id text)` | Get transfer items |

### 2.8 Specialization & Skills (7 functions)

| Function | Purpose |
|----------|---------|
| `get_learned_building_sets(in_account_id bigint)` | Get learned sets |
| `get_learned_new_buildable_pieces(in_account_id bigint)` | Get learned pieces |
| `initialize_specialization_keystones(in_keystones text[])` | Initialize keystones |
| `purchase_specialization_keystone(in_player_id bigint, in_keystone text)` | Purchase keystone |
| `reset_specialization_keystones(in_player_id bigint)` | Reset keystones |
| `reset_specialization_tracks(in_player_id bigint)` | Reset tracks |
| `set_specialization_xp_and_level(in_player_id bigint, in_track_type dune.specializationtracktype, in_xp_amount integer, in_level real)` | Set XP/level |
| `update_specialization_refund_id(in_player_id bigint, in_refund_id smallint, in_removed_keystones smallint[])` | Update refund |
| `get_player_specialization(in_player_controller_id bigint)` | Get specialization |
| `get_player_keystones(in_player_controller_id bigint)` | Get keystones |

### 2.9 Landsraad & Politics (25 functions)

| Function | Purpose |
|----------|---------|
| `landsraad_cast_vote(in_term_id bigint, in_player_id bigint, in_decree_name text)` | Cast vote |
| `landsraad_change_term_end_time(end_term_id bigint, new_end_time timestamp, in_test_term boolean)` | Change term end |
| `landsraad_check_task_completion()` | Check task completion |
| `landsraad_check_term_won()` | Check term won |
| `landsraad_collect_task_telemetry_for_faction(in_term_id bigint, in_faction_name text)` | Collect telemetry |
| `landsraad_collect_term_telemetry(in_term_id bigint, in_faction_names text[])` | Collect term telemetry |
| `landsraad_collect_term_telemetry_for_faction(in_term_id bigint, in_faction_name text)` | Collect for faction |
| `landsraad_collect_vote_telemetry(in_term_id bigint, in_winning_faction_id integer)` | Collect vote telemetry |
| `landsraad_collect_votes(in_term_id bigint)` | Collect votes |
| `landsraad_determine_winner(in_term_id bigint)` | Determine winner |
| `landsraad_force_end_term(end_term_id bigint)` | Force end term |
| `landsraad_has_term_of_task_ended(in_task_id bigint)` | Check task ended |
| `landsraad_initialize_system(...)` | Initialize system |
| `landsraad_initialize_term(...)` | Initialize term |
| `landsraad_insert_task_progress(in_term_id bigint, in_player_id bigint, ...)` | Insert progress |
| `landsraad_insert_task_progress_batched(in_term_id bigint, in_task_progress dune.landsraadtaskprogress[])` | Batch insert |
| `landsraad_insert_task_progress_faction(in_term_id bigint, in_faction_name text, ...)` | Insert faction progress |
| `landsraad_insert_task_progress_random(in_term_id bigint, in_faction_names text[], in_num_rows integer)` | Random progress |
| `landsraad_load_current_rotation(in_term_id bigint)` | Load rotation |
| `landsraad_load_current_term()` | Load current term |
| `landsraad_load_guild_contribution(in_term_id bigint, in_guild_id bigint, in_faction_id bigint)` | Load guild contribution |
| `landsraad_load_guild_contributions(in_term_id bigint, in_num_guilds integer, in_faction_names text[])` | Load contributions |
| `landsraad_load_guild_vote(in_term_id bigint, in_player_id bigint)` | Load guild vote |
| `landsraad_load_house_rewards(in_player_id bigint)` | Load house rewards |
| `landsraad_load_player_contributions(in_term_id bigint, in_player_ids bigint[])` | Load contributions |
| `landsraad_load_task_faction_progress(in_term_id bigint)` | Load task progress |
| `landsraad_load_task_faction_reveal_state(in_term_id bigint)` | Load reveal state |
| `landsraad_load_term_progress(in_term_id bigint, in_num_guilds integer, ...)` | Load term progress |
| `landsraad_notify_house_rewards_changed()` | Notify rewards |
| `landsraad_perform_daily_task_reveal(in_term_id bigint, in_faction_names text[], ...)` | Daily reveal |
| `landsraad_process_house_rewards()` | Process rewards |
| `landsraad_process_task_progress(max_rows integer)` | Process progress |
| `landsraad_task_has_been_completed(in_task_id bigint)` | Check completed |
| `landsraad_update_task_faction_reveal_state(in_term_id bigint, in_task_board_index integer, faction_name text, reveal_state boolean)` | Update reveal |
| `landsraad_withdraw_house_reward(in_player_id bigint, in_house_rewards dune.landsraadplayerhousereward[])` | Withdraw reward |
| `get_player_landsraad(in_player_controller_id bigint)` | Get Landsraad data |

### 2.10 World & Partitions (30 functions)

| Function | Purpose |
|----------|---------|
| `add_partition_unique(in_map text, in_definition jsonb, in_dimension bigint, in_label text)` | Add partition |
| `determine_partition_label(in_map text, in_dimension_index integer, in_label text, in_allow_overwrite boolean, in_partition_id bigint)` | Determine label |
| `determine_partition_label_trigger()` | Label trigger |
| `get_partition_presets()` | Get presets |
| `get_partitions(in_map text)` | Get partitions for map |
| `igwo_delete_world_partitions(in_partition_ids bigint[])` | Delete partitions |
| `igwo_get_partition_id_seq_last_value()` | Get sequence value |
| `igwo_get_partition_ids()` | Get partition IDs |
| `igwo_get_partitions()` | Get all partitions |
| `igwo_get_server_details()` | Get server details |
| `igwo_insert_world_partition(in_partition_id bigint, in_map text, in_partition_definition jsonb, ...)` | Insert partition |
| `igwo_next_partition_id_seq()` | Next sequence |
| `igwo_notify_world_partition_update()` | Notify update |
| `igwo_restart_partition_id_seq(in_restart_with bigint)` | Restart sequence |
| `igwo_update_world_partition(in_map text, in_partition_definition jsonb, in_partition_id bigint, ...)` | Update partition |
| `initialize_partitions_basic_battlegroup()` | Init basic BG |
| `initialize_partitions_basic_survival_1()` | Init survival |
| `initialize_partitions_development_battlegroup()` | Init development |
| `initialize_partitions_editor_default_1x1()` | Init editor |
| `initialize_partitions_full_battlegroup()` | Init full BG |
| `initialize_partitions_igw_test_small_2x1()` | Init test 2x1 |
| `initialize_partitions_igw_test_small_2x2()` | Init test 2x2 |
| `initialize_partitions_igw_training()` | Init training |
| `initialize_world_partition(in_map_name text, in_num_servers integer, in_dimension_index integer)` | Init partition |
| `load_dimension_index(in_map text, in_partition_id bigint)` | Load dimension |
| `load_partition_definition_map()` | Load definition map |
| `load_world_partition(in_map_name text, in_server_id text, in_desired_dimension_index bigint, in_desired_partition_id bigint)` | Load partition |
| `save_world_partition(in_map_name text, in_server_id text, in_dimension_index bigint, ...)` | Save partition |
| `unassign_partition(in_server_id text)` | Unassign partition |
| `update_partition_labels(in_allow_overwrite boolean)` | Update labels |
| `get_battlegroup_close_date()` | Get close date |
| `set_battlegroup_close_date(in_close_date timestamp)` | Set close date |

### 2.11 Spice Fields & Coriolis (24 functions)

| Function | Purpose |
|----------|---------|
| `corilis_cleanup_map(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)` | Cleanup map |
| `coriolis_cleanup_farm(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)` | Cleanup farm |
| `coriolis_cleanup_partition(in_server_info dune.serverinfo, in_map_info dune.coriolismapinfo)` | Cleanup partition |
| `coriolis_update_seed(in_server_info dune.serverinfo, in_new_coriolis_seed integer, in_map_info dune.coriolismapinfo)` | Update seed |
| `debug_set_farm_seed(in_new_coriolis_seed integer)` | Set farm seed |
| `debug_set_map_seed(in_map text, in_new_coriolis_seed integer)` | Set map seed |
| `debug_set_partition_seed(in_partition_id bigint, in_new_coriolis_seed integer)` | Set partition seed |
| `fetch_resourcefield_state(in_map text, in_dimension_index integer, in_field_kind_id smallint)` | Fetch field state |
| `fetch_server_spice_field_manifest(in_server_id text)` | Fetch spice manifest |
| `fetch_spicefie_id_types_with_global_info(in_map_name text, in_dimension_index integer)` | Fetch spice types |
| `get_farm_state()` | Get farm state |
| `get_stored_user_data_encryption_key_hash()` | Get encryption key |
| `get_stored_user_data_encryption_status()` | Get encryption status |
| `get_stored_user_data_encryption_taint_xmax()` | Get taint status |
| `produce_spicefield_manifest(in_map_name text, in_dimension_index integer)` | Produce manifest |
| `record_deactivated_spice_field(in_server_id text, in_spicefield_type_id integer)` | Record deactivated |
| `record_static_shifting_sand(in_id text, in_alpha double precision, ...)` | Record shifting sand |
| `record_unreadied_spice_fields(in_server_id text, in_spicefield_type_id integer, in_num_unreadied integer)` | Record unreadied |
| `request_spawn_spice_field(in_server_id text, in_spicefield_type_id integer)` | Request spawn |
| `reset_global_spice_field_state(in_map_name text, in_dimension_index integer)` | Reset state |
| `retrieve_all_static_shifting_sand()` | Retrieve all sand |
| `try_prime_spicefield(in_source_server_id text, in_spicefield_id integer)` | Try prime |
| `try_restart_spicefield(in_server_id text, in_spicefield_type_id integer)` | Try restart |
| `try_spawn_spicefield(in_source_server_id text, in_spicefield_id integer)` | Try spawn |
| `try_update_exchange_categories_hash(in_new_hash integer)` | Update hash |
| `update_global_spice_field_rules(in_max_globally_primed integer, in_max_globally_active integer, in_spicefield_type_id integer)` | Update rules |
| `update_spice_field_spawn_state(in_is_spawning_active boolean, in_spicefield_type_id integer)` | Update spawn state |
| `upsert_spicefield_types(in_max_globally_active integer[], ...)` | Upsert types |

### 2.12 Chat & Communication (18 functions)

| Function | Purpose |
|----------|---------|
| `add_event_log_data(in_game_event_owner bigint, in_universe_time bigint, ...)` | Add event log |
| `add_event_log_data_batched(in_data dune.eventlogbulkentrydata[])` | Batch add events |
| `add_map_areas_surveyed_items(in_account_id bigint, in_area_id smallint, ...)` | Add surveyed items |
| `add_map_areas_time_discovered(in_account_id bigint, in_area_id smallint, ...)` | Add discovered time |
| `add_map_areas_time_first_entered(in_account_id bigint, in_area_id smallint, ...)` | Add first entered |
| `clean_expired_party_invites(in_invite_expire_seconds integer)` | Clean expired invites |
| `create_event_log_partition()` | Create log partition |
| `delete_all_static_shifting_sand()` | Delete all sand |
| `get_all_player_travel_states()` | Get travel states |
| `get_online_player_controller_ids(in_map text)` | Get online on map |
| `get_online_player_controller_ids_on_farm()` | Get online on farm |
| `get_player_online_state_within_grace_period_for_each_server()` | Get grace period |
| `load_events_log_data_from_player(in_actor_id bigint, in_limit_entries_num integer)` | Load player events |
| `log_cheating(in_fls_id text, in_cheat_type dune.cheat_type_enum, in_event_time timestamp)` | Log cheating |
| `log_event_solaris(in_function_oid oid, in_message dune.logmessagetype, ...)` | Log Solari event |
| `set_all_inactive_players_in_farm_offline()` | Set inactive offline |
| `set_players_from_server_ids_offline(in_server_ids text[])` | Set servers offline |
| `wipe_old_events_log(in_days_limit integer)` | Wipe old logs |
| `get_active_servers_for_gateway()` | Get active servers |

### 2.13 Account & Authentication (25 functions)

| Function | Purpose |
|----------|---------|
| `can_takeover_account(in_user_id text)` | Check takeover |
| `cleanup_account_log_and_orphaned_actors()` | Cleanup orphans |
| `cleanup_accounts_marked_for_deletion_in_fls(in_account_ids text[])` | Cleanup FLS deletes |
| `decrypt_user_data(in_encrypted_data bytea)` | Decrypt data |
| `delete_account(in_user_id text, in_reason text)` | Delete account |
| `dune_get_account_id_by_user(in_user text)` | Get account by user |
| `encrypt_user_data(in_data text)` | Encrypt data |
| `get_account_actor_ids(in_account_id bigint)` | Get account actors |
| `get_controller_id_from_platform_id(in_platform_id text)` | Get controller ID |
| `get_encrypted_account(...)` | Get encrypted account |
| `get_friends_search(in_player_name text, in_max_players_count integer)` | Search friends |
| `get_player_infos_for_character_names(in_character_names text[])` | Get by character name |
| `get_player_infos_for_fls_ids(in_fls_ids text[])` | Get by FLS ID |
| `get_player_infos_for_funcom_ids(in_funcom_ids text[])` | Get by Funcom ID |
| `get_player_pawn(in_account_id bigint)` | Get player pawn |
| `get_takeoverable_user_ids()` | Get takeoverable IDs |
| `load_takeoverable_user_ids()` | Load takeoverable |
| `login_account(in_user_id text, in_funcom_id text, ...)` | Login account |
| `perform_notify_on_character_delete(in_user_id text)` | Notify on delete |
| `set_account_as_takeoverable(in_user_id text, in_new_user_id text)` | Set takeoverable |
| `takeover_account(in_user_to_takeover text, in_current_user text)` | Takeover account |
| `update_returning_player_status(in_user_id text, in_minimum_returning_player_time_seconds integer)` | Update returning |
| `get_demo_state(in_user_id text)` | Get demo state |
| `set_demo_state(in_user_id text, in_demo_state dune.demostate)` | Set demo state |
| `save_demo_account_time(in_fls_id text, in_demo_playtime_seconds integer)` | Save demo time |

### 2.14 Markers & Map Data (20 functions)

| Function | Purpose |
|----------|---------|
| `create_sinkchart_for_map_area_id(in_item_id bigint, in_creator_id bigint, ...)` | Create sinkchart |
| `delete_map_markers(in_dimension_index integer, in_map_name text, in_player_marker_data dune.deleteplayermarkerdata[])` | Delete markers |
| `delete_markers_by_id(in_marker_ids integer[])` | Delete by ID |
| `delete_markers_by_static_location_key(p_location_key text)` | Delete by location |
| `delete_markers_for_all_players(in_marker_types_to_keep text[], in_map text)` | Delete for all |
| `delete_markers_return_actor_ids(in_dimension_index integer, in_map_name text, in_marker_ids integer[])` | Delete and return |
| `delete_static_location_markers(p_location_keys text[])` | Delete static |
| `load_markers(in_player_id bigint, in_dimension_id integer, in_map_name text)` | Load markers |
| `load_map_areas_entries(in_account_id bigint, in_map_name text)` | Load map areas |
| `save_markers(in_player_marker_data dune.saveplayermarkerdata[], in_marker_data dune.savemarkerdata[])` | Save markers |
| `update_marker_ids(in_old_ids integer[], in_new_ids integer[])` | Update marker IDs |
| `use_sinkchart(in_player_id bigint, in_account_id bigint, in_area_id smallint, ...)` | Use sinkchart |
| `clear_map_areas_data_for_player(in_id bigint)` | Clear map data |
| `get_map_areas_entries(in_account_id bigint, in_map_name text)` | Get map areas |
| `load_static_encounter_name(in_map_name text, in_package_name text, in_actor_name text)` | Load encounter |
| `save_static_encounter_name(in_map_name text, in_package_name text, in_actor_name text, in_encounter_name text)` | Save encounter |
| `save_static_encounter_waiting_for_reset(in_map_name text, in_package_name text, in_actor_name text, in_waiting_for_reset boolean)` | Save waiting reset |
| `upgrade_location_data_list(in_location_data_list jsonb, in_map_field_name text)` | Upgrade location |
| `upgrade_map_name(in_map_name text)` | Upgrade map name |
| `upgrade_map_value(in_value jsonb)` | Upgrade map value |
| `downgrade_map_name(in_map_name text)` | Downgrade map name |

### 2.15 Permissions & Ownership (16 functions)

| Function | Purpose |
|----------|---------|
| `get_permission_actors_for_server(in_server_info dune.serverinfo)` | Get server permissions |
| `get_permission_for_actor(in_actor_id bigint)` | Get actor permission |
| `get_permission_for_actors(in_actor_id bigint[])` | Get actors permissions |
| `get_permission_for_player_actors(in_player_id bigint, in_min_rank smallint)` | Get player permissions |
| `ownership_handle_actor_delete(in_player_id bigint)` | Handle ownership delete |
| `permission_actor_create_or_update_base_marker(in_actor_id bigint, in_player_id bigint, in_rank smallint)` | Create marker |
| `permission_actor_destroy(in_actor_id bigint)` | Destroy permission |
| `permission_actor_register(in_entry dune.actorpermissionentry, in_owner_rank dune.actorpermissionrankdata)` | Register permission |
| `permission_actor_takeover(in_entry dune.actorpermissionentry, in_owner_rank dune.actorpermissionrankdata)` | Takeover permission |
| `permission_actor_update_marker_location(in_actor_id bigint, in_location_x real, in_location_y real, in_location_z real)` | Update location |
| `permission_remove_player_rank(in_actor_id bigint, in_player_id bigint)` | Remove rank |
| `permission_set_access_level(in_actor_id bigint, in_access_level smallint)` | Set access level |
| `permission_set_name(in_actor_id bigint, in_name text)` | Set name |
| `permission_set_player_rank(in_actor_id bigint, in_player_id bigint, in_rank smallint, in_map_id text)` | Set player rank |
| `gather_ownerless_actors_on_server(in_server_info dune.serverinfo)` | Gather ownerless |
| `gather_player_linked_actors(in_player_pawn_id bigint)` | Gather linked actors |
| `gather_removed_accounts_that_left_orphaned_actors_on_server(in_server_info dune.serverinfo)` | Gather orphans |
| `cleanup_orphaned_entities()` | Cleanup orphans |

### 2.16 Travel & Movement (17 functions)

| Function | Purpose |
|----------|---------|
| `get_traveling_actor_id_and_types(in_actor_id bigint)` | Get traveling actor |
| `get_traveling_actor_ids(in_actor_id bigint, in_max_recursion_level integer)` | Get traveling IDs |
| `get_traveling_actors_fls_ids(in_actor_id bigint)` | Get traveling FLS IDs |
| `get_traveling_non_player_actor_ids(in_actor_id bigint)` | Get non-player IDs |
| `load_travel_return_info(in_player_controller_id bigint)` | Load return info |
| `load_travel_to_player_info(in_player_controller_id bigint)` | Load travel info |
| `remove_aborted_authority_transfer_actors(in_partition_id bigint)` | Remove aborted |
| `save_aborted_authority_transfer_actors(in_actor_ids bigint[], in_partition_id bigint)` | Save aborted |
| `save_actor_dislocation(in_actor_id bigint, in_current_server_info dune.serverinfo, in_target_location vector, in_target_dimension_index integer)` | Save dislocation |
| `save_travel_return_info(in_player_controller_id bigint, in_map text, in_transform dune.transform)` | Save return info |
| `update_traveling_actor_dependencies(in_dep dune.traveldependency[])` | Update dependencies |
| `update_traveling_actor_tree(in_actor_id bigint, in_target_transform dune.transform, ...)` | Update actor tree |
| `get_actors_location_data_with_permission(in_actor_ids bigint[])` | Get location data |
| `get_actor_server_info(in_id bigint)` | Get server info |
| `server_info_match(in_actor dune.actors, in_server_info dune.serverinfo)` | Match server info |
| `delete_actors_and_respawns_on_server(in_server_info dune.serverinfo, ...)` | Delete on server |
| `mark_server_dead(in_server_id text)` | Mark server dead |

### 2.17 Utility & Helper Functions (30+ functions)

| Function | Purpose |
|----------|---------|
| `assign_actor_id(in_class text)` | Assign actor ID |
| `add_actor_audit(in_id bigint, in_class text)` | Add actor audit |
| `delete_actors(in_ids bigint[])` | Delete actors |
| `delete_actor_states_travel(in_actor_id bigint)` | Delete travel state |
| `delete_all_dungeon_completions(in_dungeon_id text)` | Delete completions |
| `delete_all_dungeon_completions_by_player(in_dungeon_id text, in_player_id bigint, ...)` | Delete by player |
| `delete_all_dungeon_completions_for_all_dungeons_by_player(in_player_id bigint, ...)` | Delete all dungeons |
| `delete_dialogue_data(in_player_controller_id bigint)` | Delete dialogue |
| `delete_world_partition_by_map_id(in_map_id text)` | Delete partition |
| `find_actor_by_id(in_id bigint)` | Find actor |
| `fix_broken_harkonnen_players_due_to_fooled_thufir()` | Fix Harkonnen bug |
| `get_actor_server_info(in_id bigint)` | Get actor server |
| `get_all_player_character_home_dimensions()` | Get home dimensions |
| `get_best_dungeon_completion(in_dungeon_id text)` | Get best completion |
| `get_best_dungeons_completions_for_player(in_player_id bigint)` | Get best dungeons |
| `get_dungeon_completion(in_dungeon_id text, in_player_id bigint)` | Get completion |
| `get_partition_id_for_server(in_server_id text)` | Get partition ID |
| `get_player_partition_id(in_fls_id text)` | Get player partition |
| `get_registered_spawned_actor(in_spawner_id bigint)` | Get spawned actor |
| `get_respawn_locations(in_account_id bigint)` | Get respawn locations |
| `get_universe_time()` | Get universe time |
| `get_vehicle_id(in_actor_id bigint, in_class text)` | Get vehicle ID |
| `load_full_actors(in_ids bigint[])` | Load full actors |
| `record_dungeon_completion(in_dungeon_id text, in_difficulty integer, in_duration_ms integer, players_ids bigint[])` | Record completion |
| `register_spawned_actor(in_spawner_id bigint, in_actor_id bigint)` | Register spawned |
| `reset_all_players_from_server_ids_grace_period_and_logoff_timer(in_server_id text, in_reset_time timestamp)` | Reset grace period |
| `save_actors(in_server_info dune.serverinfo, in_actors dune.actordescription[], in_actor_state dune.actorstate)` | Save actors |
| `save_player(in_player dune.playerdescription)` | Save player |
| `save_player_pawn(in_pawn dune.actordescription, in_server_info dune.serverinfo, in_life_state dune.playerlifestate)` | Save pawn |
| `update_farm_state(in_server_id text, in_outgoing_s2s_connections integer, ...)` | Update farm state |
| `update_server_building_favorites(in_account_id bigint, in_building_types text[])` | Update favorites |
| `update_server_learned_building_sets(in_account_id bigint, in_learned_building_sets text[])` | Update learned sets |
| `update_server_learned_new_buildable_pieces(in_account_id bigint, in_new_buildable_pieces text[])` | Update learned pieces |
| `update_universe_time(in_farm_id text)` | Update universe time |
| `zero_transform()` | Zero transform |
| `get_applied_patches()` | Get applied patches |
| `get_universe_time()` | Get universe time |

---

## 3. RabbitMQ Exchanges & Queues

### 3.1 Game Exchanges (mq-game at port 32716)

| Exchange | Type | Purpose |
|----------|------|---------|
| `heartbeats` | direct | In-game broadcasts and notifications |
| `rpc` | direct | Server RPC calls (currently no bindings) |
| `notifications` | topic | General notifications |
| `chat.faction.1-4` | fanout | Faction chat channels (4 factions) |
| `chat.guild.*` | fanout | Guild chat channels |
| `chat.intercept` | topic | Chat intercept/filtering |
| `chat.proximity` | direct | Proximity-based chat |
| `chat.whispers` | direct | Private whispers |
| `chat.map` | direct | Map-wide chat |
| `login_grant` | direct | Login grant messages |
| `login_request` | direct | Login requests |
| `login_response` | direct | Login responses |
| `status.*` | fanout | Per-map status (Overmap, Survival_1, DeepDesert_1, etc.) |
| `travel_queue_status` | topic | Travel queue updates |
| `director_respawned` | fanout | Respawn events from director |

### 3.2 Admin Exchanges (mq-admin at port 30325)

| Exchange | Type | Messages Published | Purpose |
|----------|------|-------------------|---------|
| `completions` | direct | 723 | Completion events |
| `response` | direct | 64K+ | Response routing |
| `settingsUpdate` | fanout | 71 | Server settings updates |
| `travel` | topic | - | Travel messages |
| `travelQueueStatus` | fanout | 1K+ | Travel queue status |
| `grant` | direct | - | Grant messages |
| `heartbeats` | direct | 2K+ | Heartbeat messages |
| `rpc` | direct | - | RPC messages |
| `director_respawned` | fanout | - | Respawn events |

### 3.3 Game Queues

| Queue | Consumers | Purpose |
|-------|-----------|---------|
| `B17A5F036D1F7882_queue` | - | Host-specific queue |
| `bgdRpc` | 1 | BGD RPC responses |
| `loginRequests` | 1 | Login request queue |
| `queue.intercept` | 1 | Chat intercept queue |
| `queue.server.*` (5 queues) | 1 each | Per-server queues |

---

## 4. BGD Director API Endpoints

### 4.1 Player Endpoints

| Endpoint | Method | Response | Purpose |
|----------|--------|----------|---------|
| `/v0/players` | GET | `["FLS_ID"]` | List all player FLS IDs |
| `/v0/players/online` | GET | `["FLS_ID"]` | List online players |
| `/v0/players/intransit` | GET | `[]` | Players in transit |
| `/v0/players/graceperiod` | GET | `[]` | Players in grace period |
| `/v0/players/completion` | GET | `[]` | Completion queue |
| `/v0/players/queued` | GET | `[]` | Queued players |

### 4.2 Battlegroup Endpoints

| Endpoint | Method | Response | Purpose |
|----------|--------|----------|---------|
| `/v0/battlegroup` | GET | Full JSON | Complete battlegroup state (maps, servers, players, configs) |
| `/` | GET | HTML | Web dashboard UI |

### 4.3 FLS Settings Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v0/BattlegroupFetchFlsReportSettings` | GET | Fetch FLS report settings |
| `/v0/BattlegroupUpdateFlsReportSettings` | POST | Update FLS report settings |
| `/v0/BattlegroupClearFlsReportOverrides` | POST | Clear FLS overrides |

### 4.4 Battlegroup JSON Structure

The `/v0/battlegroup` endpoint returns:
- `dimensionMaps[]` — Multi-server maps with partitions
- `singleServerMaps[]` — Single-server maps
- `instancedMaps[]` — Instanced content (dungeons, gyms, etc.)
- Per-server data: `partition`, `ip`, `gamePort`, `numPlayers*`, `status`, `cfg`, `lastServerState`
- `serverGameplaySettings`: hydration, sandstorm, sandworm, PvP, security zones, mining multiplier, durability

### 4.5 Map Types Managed by BGD

- **Survival** — Survival mode maps
- **Story** — Story mission maps
- **Challenge Rooms** — Combat challenges
- **CB (Combat Block)** — PvP combat zones
- **DLC Content** — DLC-specific maps
- **Test Gyms** — Testing/training areas
- **Overmap** — Main overworld
- **Deep Desert** — Endgame PvP zone
- **Arrakeen** — City zone
- **Harko Village** — NPC village

---

## 5. Kubernetes Resources

### 5.1 World Namespace Pods

| Pod Pattern | Purpose |
|-------------|---------|
| `{world}-mq-admin-sts-0` | RabbitMQ admin instance |
| `{world}-mq-game-sts-0` | RabbitMQ game instance |
| `{world}-tr-deploy-*` | Text Router (RMQ auth) |
| `{world}-bgd-deploy-*` | Battlegroup Director |
| `{world}-sgw-deploy-*` | Server Gateway |
| `{world}-db-dbdepl-*` | PostgreSQL database |
| `{world}-fb-deploy-*` | File Browser |
| `{world}-sg-overmap-pod-*` | Overmap game server |
| `{world}-sg-survival-1-pod-*` | Survival game server |
| `{world}-sg-deepdesert-1-pod-*` | Deep Desert server |
| `{world}-sg-arrakeen-pod-*` | Arrakeen server |
| `{world}-sg-harkovillage-pod-*` | Harko Village server |

### 5.2 Operator Deployments (funcom-operators namespace)

| Deployment | Purpose |
|------------|---------|
| `battlegroupoperator-controller-manager` | Manages BattleGroup CRDs |
| `databaseoperator-controller-manager` | Manages database lifecycle |
| `serveroperator-controller-manager` | Manages ServerGroup CRDs |
| `utilitiesoperator-controller-manager` | Manages utility services |

### 5.3 Services (NodePort)

| Service | NodePort | Purpose |
|---------|----------|---------|
| `bgd-svc` | 30553 | BGD Director API |
| `mq-admin-svc` | 30325 | RMQ Admin Management UI |
| `mq-admin-svc` | 32729 | RMQ Admin AMQP (TLS) |
| `mq-game-svc` | 32716 | RMQ Game Management UI |
| `mq-game-svc` | 31982 | RMQ Game AMQP (TLS) |

---

## 6. Game Tables Reference

### 6.1 Core Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `encrypted_accounts` | 10 | Encrypted account data |
| `encrypted_player_state` | 10 | Encrypted player state |
| `actors` | 411 | All game entities (players, NPCs, vehicles, buildings) |
| `items` | 1,482 | Inventory items |
| `inventories` | 459 | Inventory containers |
| `buildings` | 8 | Player buildings |
| `vehicles` | 16 | Player vehicles |
| `guilds` | 1 | Guilds |
| `factions` | 4 | Factions (Atreides, Harkonnen, Fremen, Corrino) |
| `bans` | 0 | Banned players |
| `game_events` | 76 | Game event log |

### 6.2 Configuration Tables

| Table | Rows | Purpose |
|-------|------|---------|
| `world_partition` | 30 | Server partition configuration |
| `dune_exchanges` | 1 | Exchange configuration |
| `landsraad_decrees` | 11 | Landsraad decrees |
| `landsraad_tasks` | 25 | Landsraad tasks |

### 6.3 Dashboard Tables

| Table | Purpose |
|-------|---------|
| `dashboard.bans` | Ban records with duration/reason |
| `dashboard.player_actions` | Admin action audit log |
| `dashboard.player_ips` | Player IP address tracking |
| `dashboard.chat_history` | Chat message archive |

---

## Appendix: Common Admin Workflows

### A.1 Ban a Player
1. Search for player by name
2. Get player_controller_id
3. Call `POST /api/ban_player` with duration and reason
4. Optionally detect player IP and apply iptables block

### A.2 Teleport a Player
1. Ensure player is offline (check online status)
2. Get partition ID from `GET /api/admin-experimental/partitions`
3. Call `POST /api/admin-experimental/teleport` with FLS ID, partition ID, coordinates

### A.3 Send In-Game Broadcast
1. Go to Admin Experimental tab
2. Enter title, message, duration
3. Click "Send Broadcast"
4. Message appears for all connected players

### A.4 Fix a Stuck Player
1. Search for player
2. Check online status
3. If stuck: set offline via `set_players_from_server_ids_offline`
4. Teleport to safe location
5. Reset vitals if needed

### A.5 Investigate Cheating
1. Search for player
2. View player stats (check for impossible values)
3. View inventory (check for duped items)
4. If confirmed: `flag_player_as_cheater`
5. Ban player and block IP

---

**End of Reference**
