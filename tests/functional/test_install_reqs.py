import os
import textwrap

import pytest

from tests.lib import (
    _create_test_package_with_subdirectory,
    path_to_url,
    pyversion,
    requirements_file,
)
from tests.lib.local_repos import local_checkout


@pytest.mark.network
def test_requirements_file(script):
    """
    Test installing from a requirements file.

    """
    other_lib_name, other_lib_version = 'anyjson', '0.3'
    script.scratch_path.joinpath("initools-req.txt").write_text(textwrap.dedent("""\
        INITools==0.2
        # and something else to test out:
        %s<=%s
        """ % (other_lib_name, other_lib_version)))
    result = script.pip(
        'install', '-r', script.scratch_path / 'initools-req.txt'
    )
    assert (
        script.site_packages / 'INITools-0.2-py%s.egg-info' %
        pyversion in result.files_created
    )
    assert script.site_packages / 'initools' in result.files_created
    assert result.files_created[script.site_packages / other_lib_name].dir
    fn = '%s-%s-py%s.egg-info' % (other_lib_name, other_lib_version, pyversion)
    assert result.files_created[script.site_packages / fn].dir


def test_schema_check_in_requirements_file(script):
    """
    Test installing from a requirements file with an invalid vcs schema..

    """
    script.scratch_path.joinpath("file-egg-req.txt").write_text(
        "\n%s\n" % (
            "git://github.com/alex/django-fixture-generator.git"
            "#egg=fixture_generator"
        )
    )

    with pytest.raises(AssertionError):
        script.pip(
            "install", "-vvv", "-r", script.scratch_path / "file-egg-req.txt"
        )


def test_relative_requirements_file(script, data):
    """
    Test installing from a requirements file with a relative path. For path
    URLs, use an egg= definition.

    """
    egg_info_file = (
        script.site_packages / 'FSPkg-0.1.dev0-py%s.egg-info' % pyversion
    )
    egg_link_file = (
        script.site_packages / 'FSPkg.egg-link'
    )
    package_folder = script.site_packages / 'fspkg'

    # Compute relative install path to FSPkg from scratch path.
    full_rel_path = data.packages.joinpath('FSPkg') - script.scratch_path
    full_rel_url = 'file:' + full_rel_path + '#egg=FSPkg'
    embedded_rel_path = script.scratch_path.joinpath(full_rel_path)

    # For each relative path, install as either editable or not using either
    # URLs with egg links or not.
    for req_path in (full_rel_path, full_rel_url, embedded_rel_path):
        req_path = req_path.replace(os.path.sep, '/')
        # Regular install.
        with requirements_file(req_path + '\n',
                               script.scratch_path) as reqs_file:
            result = script.pip('install', '-vvv', '-r', reqs_file.name,
                                cwd=script.scratch_path)
            assert egg_info_file in result.files_created, str(result)
            assert package_folder in result.files_created, str(result)
            script.pip('uninstall', '-y', 'fspkg')

        # Editable install.
        with requirements_file('-e ' + req_path + '\n',
                               script.scratch_path) as reqs_file:
            result = script.pip('install', '-vvv', '-r', reqs_file.name,
                                cwd=script.scratch_path)
            assert egg_link_file in result.files_created, str(result)
            script.pip('uninstall', '-y', 'fspkg')


@pytest.mark.network
@pytest.mark.svn
def test_multiple_requirements_files(script, tmpdir):
    """
    Test installing from multiple nested requirements files.

    """
    other_lib_name, other_lib_version = 'anyjson', '0.3'
    script.scratch_path.joinpath("initools-req.txt").write_text(
        textwrap.dedent("""
            -e %s@10#egg=INITools
            -r %s-req.txt
        """) %
        (
            local_checkout(
                'svn+http://svn.colorstudy.com/INITools/trunk',
                tmpdir.joinpath("cache"),
            ),
            other_lib_name
        ),
    )
    script.scratch_path.joinpath("%s-req.txt" % other_lib_name).write_text(
        "%s<=%s" % (other_lib_name, other_lib_version)
    )
    result = script.pip(
        'install', '-r', script.scratch_path / 'initools-req.txt'
    )
    assert result.files_created[script.site_packages / other_lib_name].dir
    fn = '%s-%s-py%s.egg-info' % (other_lib_name, other_lib_version, pyversion)
    assert result.files_created[script.site_packages / fn].dir
    assert script.venv / 'src' / 'initools' in result.files_created


def test_package_in_constraints_and_dependencies(script, data):
    script.scratch_path.joinpath("constraints.txt").write_text(
        "TopoRequires2==0.0.1\nTopoRequires==0.0.1"
    )
    result = script.pip('install', '--no-index', '-f',
                        data.find_links, '-c', script.scratch_path /
                        'constraints.txt', 'TopoRequires2')
    assert 'installed TopoRequires-0.0.1' in result.stdout


def test_multiple_constraints_files(script, data):
    script.scratch_path.joinpath("outer.txt").write_text("-c inner.txt")
    script.scratch_path.joinpath("inner.txt").write_text(
        "Upper==1.0")
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'outer.txt', 'Upper')
    assert 'installed Upper-1.0' in result.stdout


def test_respect_order_in_requirements_file(script, data):
    script.scratch_path.joinpath("frameworks-req.txt").write_text(textwrap.dedent("""\
        parent
        child
        simple
        """))

    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-r',
        script.scratch_path / 'frameworks-req.txt'
    )

    downloaded = [line for line in result.stdout.split('\n')
                  if 'Processing' in line]

    assert 'parent' in downloaded[0], (
        'First download should be "parent" but was "%s"' % downloaded[0]
    )
    assert 'child' in downloaded[1], (
        'Second download should be "child" but was "%s"' % downloaded[1]
    )
    assert 'simple' in downloaded[2], (
        'Third download should be "simple" but was "%s"' % downloaded[2]
    )


def test_install_local_editable_with_extras(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    res = script.pip_install_local(
        '-e', to_install + '[bar]',
        expect_error=False,
        expect_stderr=True,
    )
    assert script.site_packages / 'easy-install.pth' in res.files_updated, (
        str(res)
    )
    assert (
        script.site_packages / 'LocalExtras.egg-link' in res.files_created
    ), str(res)
    assert script.site_packages / 'simple' in res.files_created, str(res)


def test_install_collected_dependencies_first(script):
    result = script.pip_install_local(
        'toporequires2',
    )
    text = [line for line in result.stdout.split('\n')
            if 'Installing' in line][0]
    assert text.endswith('toporequires2')


@pytest.mark.network
def test_install_local_editable_with_subdirectory(script):
    version_pkg_path = _create_test_package_with_subdirectory(script,
                                                              'version_subdir')
    result = script.pip(
        'install', '-e',
        '%s#egg=version_subpkg&subdirectory=version_subdir' %
        ('git+%s' % path_to_url(version_pkg_path),)
    )

    result.assert_installed('version-subpkg', sub_dir='version_subdir')


@pytest.mark.network
def test_install_local_with_subdirectory(script):
    version_pkg_path = _create_test_package_with_subdirectory(script,
                                                              'version_subdir')
    result = script.pip(
        'install',
        '%s#egg=version_subpkg&subdirectory=version_subdir' %
        ('git+' + path_to_url(version_pkg_path),)
    )

    result.assert_installed('version_subpkg.py', editable=False)


def test_wheel_user_with_prefix_in_pydistutils_cfg(
        script, data, with_wheel):
    if os.name == 'posix':
        user_filename = ".pydistutils.cfg"
    else:
        user_filename = "pydistutils.cfg"
    user_cfg = os.path.join(os.path.expanduser('~'), user_filename)
    script.scratch_path.joinpath("bin").mkdir()
    with open(user_cfg, "w") as cfg:
        cfg.write(textwrap.dedent("""
            [install]
            prefix=%s""" % script.scratch_path))

    result = script.pip(
        'install', '--user', '--no-index',
        '-f', data.find_links,
        'requiresupper')
    # Check that we are really installing a wheel
    assert 'Running setup.py install for requiresupper' not in result.stdout
    assert 'installed requiresupper' in result.stdout


def test_install_option_in_requirements_file(script, data, virtualenv):
    """
    Test --install-option in requirements file overrides same option in cli
    """

    script.scratch_path.joinpath("home1").mkdir()
    script.scratch_path.joinpath("home2").mkdir()

    script.scratch_path.joinpath("reqs.txt").write_text(
        textwrap.dedent(
            """simple --install-option='--home=%s'"""
            % script.scratch_path.joinpath("home1")))

    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-r',
        script.scratch_path / 'reqs.txt',
        '--install-option=--home=%s' % script.scratch_path.joinpath("home2"),
        expect_stderr=True)

    package_dir = script.scratch / 'home1' / 'lib' / 'python' / 'simple'
    assert package_dir in result.files_created


def test_constraints_not_installed_by_default(script, data):
    script.scratch_path.joinpath("c.txt").write_text("requiresupper")
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'c.txt', 'Upper')
    assert 'requiresupper' not in result.stdout


def test_constraints_only_causes_error(script, data):
    script.scratch_path.joinpath("c.txt").write_text("requiresupper")
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'c.txt', expect_error=True)
    assert 'installed requiresupper' not in result.stdout


def test_constraints_local_editable_install_causes_error(script, data):
    script.scratch_path.joinpath("constraints.txt").write_text(
        "singlemodule==0.0.0"
    )
    to_install = data.src.joinpath("singlemodule")
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'constraints.txt', '-e',
        to_install, expect_error=True)
    assert 'Could not satisfy constraints for' in result.stderr


@pytest.mark.network
def test_constraints_local_editable_install_pep518(script, data):
    to_install = data.src.joinpath("pep518-3.0")

    script.pip('download', 'setuptools', 'wheel', '-d', data.packages)
    script.pip(
        'install', '--no-index', '-f', data.find_links, '-e', to_install)


def test_constraints_local_install_causes_error(script, data):
    script.scratch_path.joinpath("constraints.txt").write_text(
        "singlemodule==0.0.0"
    )
    to_install = data.src.joinpath("singlemodule")
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'constraints.txt',
        to_install, expect_error=True)
    assert 'Could not satisfy constraints for' in result.stderr


def test_constraints_constrain_to_local_editable(script, data):
    to_install = data.src.joinpath("singlemodule")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "-e %s#egg=singlemodule" % path_to_url(to_install)
    )
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'constraints.txt', 'singlemodule')
    assert 'Running setup.py develop for singlemodule' in result.stdout


def test_constraints_constrain_to_local(script, data):
    to_install = data.src.joinpath("singlemodule")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "%s#egg=singlemodule" % path_to_url(to_install)
    )
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'constraints.txt', 'singlemodule')
    assert 'Running setup.py install for singlemodule' in result.stdout


def test_constrained_to_url_install_same_url(script, data):
    to_install = data.src.joinpath("singlemodule")
    constraints = path_to_url(to_install) + "#egg=singlemodule"
    script.scratch_path.joinpath("constraints.txt").write_text(constraints)
    result = script.pip(
        'install', '--no-index', '-f', data.find_links, '-c',
        script.scratch_path / 'constraints.txt', to_install)
    assert ('Running setup.py install for singlemodule'
            in result.stdout), str(result)


def test_double_install_spurious_hash_mismatch(
        script, tmpdir, data, with_wheel):
    """Make sure installing the same hashed sdist twice doesn't throw hash
    mismatch errors.

    Really, this is a test that we disable reads from the wheel cache in
    hash-checking mode. Locally, implicitly built wheels of sdists obviously
    have different hashes from the original archives. Comparing against those
    causes spurious mismatch errors.

    """
    # Install wheel package, otherwise, it won't try to build wheels.
    with requirements_file('simple==1.0 --hash=sha256:393043e672415891885c9a2a'
                           '0929b1af95fb866d6ca016b42d2e6ce53619b653',
                           tmpdir) as reqs_file:
        # Install a package (and build its wheel):
        result = script.pip_install_local(
            '--find-links', data.find_links,
            '-r', reqs_file.abspath, expect_error=False)
        assert 'Successfully installed simple-1.0' in str(result)

        # Uninstall it:
        script.pip('uninstall', '-y', 'simple', expect_error=False)

        # Then install it again. We should not hit a hash mismatch, and the
        # package should install happily.
        result = script.pip_install_local(
            '--find-links', data.find_links,
            '-r', reqs_file.abspath, expect_error=False)
        assert 'Successfully installed simple-1.0' in str(result)


def test_install_with_extras_from_constraints(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "%s#egg=LocalExtras[bar]" % path_to_url(to_install)
    )
    result = script.pip_install_local(
        '-c', script.scratch_path / 'constraints.txt', 'LocalExtras')
    assert script.site_packages / 'simple' in result.files_created


def test_install_with_extras_from_install(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "%s#egg=LocalExtras" % path_to_url(to_install)
    )
    result = script.pip_install_local(
        '-c', script.scratch_path / 'constraints.txt', 'LocalExtras[baz]')
    assert script.site_packages / 'singlemodule.py'in result.files_created


def test_install_with_extras_joined(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "%s#egg=LocalExtras[bar]" % path_to_url(to_install)
    )
    result = script.pip_install_local(
        '-c', script.scratch_path / 'constraints.txt', 'LocalExtras[baz]'
    )
    assert script.site_packages / 'simple' in result.files_created
    assert script.site_packages / 'singlemodule.py'in result.files_created


def test_install_with_extras_editable_joined(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "-e %s#egg=LocalExtras[bar]" % path_to_url(to_install)
    )
    result = script.pip_install_local(
        '-c', script.scratch_path / 'constraints.txt', 'LocalExtras[baz]')
    assert script.site_packages / 'simple' in result.files_created
    assert script.site_packages / 'singlemodule.py'in result.files_created


def test_install_distribution_full_union(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    result = script.pip_install_local(
        to_install, to_install + "[bar]", to_install + "[baz]")
    assert 'Running setup.py install for LocalExtras' in result.stdout
    assert script.site_packages / 'simple' in result.files_created
    assert script.site_packages / 'singlemodule.py' in result.files_created


def test_install_distribution_duplicate_extras(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    package_name = to_install + "[bar]"
    with pytest.raises(AssertionError):
        result = script.pip_install_local(package_name, package_name)
        assert 'Double requirement given: %s' % package_name in result.stderr


def test_install_distribution_union_with_constraints(script, data):
    to_install = data.packages.joinpath("LocalExtras")
    script.scratch_path.joinpath("constraints.txt").write_text(
        "%s[bar]" % to_install)
    result = script.pip_install_local(
        '-c', script.scratch_path / 'constraints.txt', to_install + '[baz]')
    assert 'Running setup.py install for LocalExtras' in result.stdout
    assert script.site_packages / 'singlemodule.py' in result.files_created


def test_install_distribution_union_with_versions(script, data):
    to_install_001 = data.packages.joinpath("LocalExtras")
    to_install_002 = data.packages.joinpath("LocalExtras-0.0.2")
    result = script.pip_install_local(
        to_install_001 + "[bar]", to_install_002 + "[baz]")
    assert ("Successfully installed LocalExtras-0.0.1 simple-3.0 " +
            "singlemodule-0.0.1" in result.stdout)


@pytest.mark.xfail
def test_install_distribution_union_conflicting_extras(script, data):
    # LocalExtras requires simple==1.0, LocalExtras[bar] requires simple==2.0;
    # without a resolver, pip does not detect the conflict between simple==1.0
    # and simple==2.0. Once a resolver is added, this conflict should be
    # detected.
    to_install = data.packages.joinpath("LocalExtras-0.0.2")
    result = script.pip_install_local(to_install, to_install + "[bar]",
                                      expect_error=True)
    assert 'installed' not in result.stdout
    assert "Conflict" in result.stderr


def test_install_unsupported_wheel_link_with_marker(script):
    script.scratch_path.joinpath("with-marker.txt").write_text(
        textwrap.dedent("""\
            %s; %s
        """) %
        (
            'https://github.com/a/b/c/asdf-1.5.2-cp27-none-xyz.whl',
            'sys_platform == "xyz"'
        )
    )
    result = script.pip(
        'install', '-r', script.scratch_path / 'with-marker.txt',
        expect_error=False,
    )

    assert ("Ignoring asdf: markers 'sys_platform == \"xyz\"' don't match "
            "your environment") in result.stdout
    assert len(result.files_created) == 0


def test_install_unsupported_wheel_file(script, data):
    # Trying to install a local wheel with an incompatible version/type
    # should fail.
    script.scratch_path.joinpath("wheel-file.txt").write_text(textwrap.dedent("""\
        %s
        """ % data.packages.joinpath("simple.dist-0.1-py1-none-invalid.whl")))
    result = script.pip(
        'install', '-r', script.scratch_path / 'wheel-file.txt',
        expect_error=True,
        expect_stderr=True,
    )
    assert ("simple.dist-0.1-py1-none-invalid.whl is not a supported " +
            "wheel on this platform" in result.stderr)
    assert len(result.files_created) == 0


def test_install_options_local_to_package(script, data):
    """Make sure --install-options does not leak across packages.

    A requirements.txt file can have per-package --install-options; these
    should be isolated to just the package instead of leaking to subsequent
    packages.  This needs to be a functional test because the bug was around
    cross-contamination at install time.
    """
    home_simple = script.scratch_path.joinpath("for-simple")
    test_simple = script.scratch.joinpath("for-simple")
    home_simple.mkdir()
    reqs_file = script.scratch_path.joinpath("reqs.txt")
    reqs_file.write_text(
        textwrap.dedent("""
            simple --install-option='--home=%s'
            INITools
            """ % home_simple))
    result = script.pip(
        'install',
        '--no-index', '-f', data.find_links,
        '-r', reqs_file,
        expect_error=True,
    )

    simple = test_simple / 'lib' / 'python' / 'simple'
    bad = test_simple / 'lib' / 'python' / 'initools'
    good = script.site_packages / 'initools'
    assert simple in result.files_created
    assert result.files_created[simple].dir
    assert bad not in result.files_created
    assert good in result.files_created
    assert result.files_created[good].dir
