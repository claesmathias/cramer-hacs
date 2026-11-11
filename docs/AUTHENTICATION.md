# Authentication and sessions

[Index](README.md) · [Operations](API_REFERENCE.md)

## Confirmed flow

`com/greenworks/basefunction/repository/LoginRepository.java`: isFleetUser/fleetAuthorization (79–88) submit `{username}` to IsFleet. fleetLogin (52–57) submits username/password to Fleet. getGucToken and switchOrganization (59–69) use organizationId to obtain GUC and Xlink credentials. Exact endpoints are declared in basefunction/api/ApiService.java; host selection is in baseframework/http/network/NetworkApi.java.

Consumer login: LoginRepository.login (91–130) submits JSON containing corp_id,email,password,resource,phone,phone_zone; the last three are null. It stores user_id/access_token/authorize/refresh_token and uses expire_in, then logs into GUC. gucLoginUrlEncoded (175 onward) uses grant_type=password with scope, client_id, client_secret, username, password, HasLocationInfo, Latitude, Longitude and LoginTime (epoch seconds). There is a multipart fallback on transport onFailure, not on every HTTP error. That repository path passes true,0,0 for location; HACS uses false,0,0. LoginActivity can also provide actual location when available.

Application key/client_secret/credential values are intentionally omitted. Constants exist in the APK and const.py; their distribution in an app does not justify reproducing them here.

## Headers and storage

RequestInterceptor.intercept (20–48) adds ApplicationKey, Language, Xlink-User-Id when present, App-Name, Brand, and Access-Token/Xlink-Access-Token when a token exists. Authorization uses Bearer Fleet for Fleet hosts and Bearer GUC elsewhere when available. It adds JSON Content-Type; Retrofit separately declares form/multipart token requests. Effective token-request headers need future verification rather than blindly copying this interceptor interaction.

Android uses SPUtils/Constant for tokens. HACS uses _base_headers and per-operation headers, an in-memory CramerAuth, config entry password and PIN options. Do not attach config entries to issues.

## Expiration and renewal

**CONFIRMED IN CODE:** LoginRepository.login uses Xlink expire_in. LoginActivity (333–377) stores Xlink expiration, sets 7200000 ms for Fleet and takes the minimum with GUC. LoginRepository.refresh sends `{refresh_token}` to Xlink `/v2/user/token/refresh` (ApiService 419–421). A method declaration does not establish that every app renewal uses it. ResponseInterceptor.intercept emits LogoutEvent on HTTP 401; it does not transparently renew tokens there.

**HACS:** authenticate branches between Fleet and consumer. Fleet XlinkToken is optional and failures are absorbed. Refresh tokens are stored, but coordinator._ensure_auth calls force_reauth with username/password 60 seconds before min(GUC,7200). refresh_guc_token performs another Fleet exchange, not an OAuth refresh grant. Device-list auth failure triggers one reauthentication; explicit MQTT credential refusal also triggers one retry. A datapoint 401 is currently hidden.

**PENDING REAL-WORLD VALIDATION:** GUC refresh_token renewal has not been reconstructed. Do not assume grant_type=refresh_token from OAuth conventions alone. Rotation/revocation, actual Fleet lifetime, organization changes and whether Xlink renews MQTT authorize remain open. Correct error classification/expiry handling first, then add only evidenced renewal operations with sanitized fixtures.
