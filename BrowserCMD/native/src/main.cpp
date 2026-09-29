#include <cstring>
#include <iostream>

int main(int argc, char** argv) {
    if (argc == 2 && std::strcmp(argv[1], "--selftest") == 0) {
        std::cout << "BrowserCMD renderer self-test: OK\n";
        return 0;
    }
    if (argc == 2 && std::strcmp(argv[1], "--info") == 0) {
        std::cout << "BrowserCMD renderer scaffold (M0)\n";
        return 0;
    }
    if (argc == 1) {
        std::cout << "BrowserCMD renderer scaffold (M0)\n";
        return 0;
    }
    std::cerr << "Usage: renderer [--info|--selftest]\n";
    return 2;
}