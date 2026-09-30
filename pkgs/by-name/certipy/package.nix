# Worked example of a tier-2 package: pure Python, normal pyproject, no build
# system heroics. Most of the backlog looks like this, which is why tier 2 is
# where the throughput is.
#
# Generated skeleton from `argos new certipy --builder python`, hashes filled
# in by `nix-init --url https://github.com/ly4k/Certipy`. The catalog entry
# claims it with `local = "certipy"`, so it counts toward coverage -- which is
# honest only because it actually builds.
{ lib
, python3Packages
, fetchFromGitHub
}:

python3Packages.buildPythonApplication rec {
  pname = "certipy";
  version = "4.8.2";
  pyproject = true;

  src = fetchFromGitHub {
    owner = "ly4k";
    repo = "Certipy";
    tag = "${version}";
    hash = "sha256-Era5iNLJkZIRvN/p3BiD/eDiDQme24G65VSG97tuEOQ=";
  };

  build-system = with python3Packages; [ setuptools ];

  # Certipy pins exact dependency versions (pyasn1==0.4.8 and friends) that are
  # older than what nixpkgs ships. It works fine against the current versions;
  # relax the pins rather than vendoring stale, unmaintained dependencies.
  pythonRelaxDeps = true;

  dependencies = with python3Packages; [
    asn1crypto
    cryptography
    impacket
    ldap3
    pyasn1
    pycryptodome
    pyopenssl
    requests
    requests-ntlm
    unicrypto
  ];

  # No test suite worth running, and what exists wants a live domain
  # controller. Import check is the useful signal here.
  doCheck = false;
  pythonImportsCheck = [ "certipy" ];

  meta = with lib; {
    description = "Active Directory Certificate Services enumeration and abuse";
    homepage = "https://github.com/ly4k/Certipy";
    license = licenses.mit;
    mainProgram = "certipy";
    maintainers = with maintainers; [ ];
    platforms = platforms.unix;
  };
}
