
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import json
chrome_options = Options()
chrome_options.add_argument("--headless")


driver = None


def begin(driver_path: str, ip: str, username: str = 'ubnt', password: str = 'ubnt'):
    global driver

    print('Starting ChromeDriver...')
    driver = webdriver.Chrome(driver_path, chrome_options=chrome_options)
    print('Driver started.')

    print('Logging in...')
    # driver.get('http:192.168.1.45/login.cgi')
    driver.get('http://{}/login.cgi'.format(ip))

    user_form = driver.find_element_by_id('username')
    pass_form = driver.find_element_by_id('password')

    user_form.send_keys(username)
    pass_form.send_keys(password)

    submit = driver.find_element_by_xpath("//input[@value='Login']")
    submit.click()
    print("(⌐■_■) We're in.")


def fetch_signal(ip: str) -> int:
    # driver.get('http:192.168.1.20/signal.cgi')
    driver.get('http://{}/signal.cgi'.format(ip))
    return json.loads(driver.find_element_by_tag_name('body').text)['signal']