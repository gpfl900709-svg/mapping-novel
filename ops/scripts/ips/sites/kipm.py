from __future__ import annotations

from ips.core.selectors import SelectorGroup
from ips.sites.base import SiteAdapter


KIPM_SITE = SiteAdapter(
    name="kipm",
    display_name="KIPM",
    web_base_url="https://kipm.kld.kr",
    api_base_url="https://kipm-api.kld.kr",
    login_path="/login",
    api_login_path="/user/login",
    api_user_info_path="/user/info",
    company_code="1000",
    cookie_domain=".kld.kr",
    auth_env_value="PROD",
    username_env_keys=("KIPM_ID", "KLD_LOGIN_ID"),
    password_env_keys=("KIPM_PW", "KLD_LOGIN_PW"),
    username_selectors=SelectorGroup(
        name="username",
        candidates=(
            "input[name='username']",
            "input#username",
            ".login__username-field input",
            "input[type='text']",
        ),
    ),
    password_selectors=SelectorGroup(
        name="password",
        candidates=(
            "input[name='password']",
            "input#password",
            ".login__password-field input",
            "input[type='password']",
        ),
    ),
    submit_selectors=SelectorGroup(
        name="submit",
        candidates=(
            "button[type='submit']",
            ".login__button",
            ".btn[type='submit']",
            "button:has-text('로그인')",
            "input[type='submit']",
        ),
    ),
)
