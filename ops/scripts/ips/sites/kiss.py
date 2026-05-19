from __future__ import annotations

from ips.core.selectors import SelectorGroup
from ips.sites.base import SiteAdapter


KISS_SITE = SiteAdapter(
    name="kiss",
    display_name="KISS",
    web_base_url="https://kiss.kld.kr",
    api_base_url="https://kiss-api.kld.kr",
    login_path="/login",
    api_login_path="/user/login",
    api_user_info_path="/user/info",
    company_code="1000",
    cookie_domain=".kld.kr",
    auth_env_value="PROD",
    username_env_keys=("KISS_ID", "KIPM_ID", "KLD_LOGIN_ID"),
    password_env_keys=("KISS_PW", "KIPM_PW", "KLD_LOGIN_PW"),
    username_selectors=SelectorGroup(
        name="username",
        candidates=(
            "input[name='username']",
            "input#username",
            "input[type='text']",
            "input[autocomplete='username']",
        ),
    ),
    password_selectors=SelectorGroup(
        name="password",
        candidates=(
            "input[name='password']",
            "input#password",
            "input[type='password']",
            "input[autocomplete='current-password']",
        ),
    ),
    submit_selectors=SelectorGroup(
        name="submit",
        candidates=(
            "button[type='submit']",
            ".btn[type='submit']",
            "button:has-text('로그인')",
            "input[type='submit']",
        ),
    ),
)
