// Project-only, file-based local Keychain bridge. stdout is a PRIVATE parent pipe.
// Do not run load directly in a terminal: it returns secret session data.
#import <Foundation/Foundation.h>
#import <Security/Security.h>
#include <unistd.h>

static const NSUInteger limit = 65536;
static NSString *const service = @"org.foot-traffic-counter.tapo-session";
static void reply(NSDictionary *value) __attribute__((noreturn));
static void reply(NSDictionary *value) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingSortedKeys error:nil];
    if (data) fwrite(data.bytes, 1, data.length, stdout);
    exit(0);
}
static void fail(NSString *code) { reply(@{@"status": code}); }
static void check(OSStatus status) {
    if (status == errSecSuccess) return;
    if (status == errSecItemNotFound) fail(@"MISSING");
    if (status == errSecInteractionNotAllowed) fail(@"SESSION_LOCKED");
    if (status == errSecAuthFailed || status == errSecUserCanceled) fail(@"STORE_DENIED");
    fail(@"STORE_ERROR");
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        if (argc != 1) fail(@"INVALID_INPUT");
        NSMutableData *input = [NSMutableData data];
        unsigned char buffer[4096];
        ssize_t count;
        while ((count = read(STDIN_FILENO, buffer, sizeof(buffer))) > 0) {
            [input appendBytes:buffer length:(NSUInteger)count];
            if (input.length > limit) fail(@"INVALID_INPUT");
        }
        if (count < 0) fail(@"INVALID_INPUT");
        id obj = [NSJSONSerialization JSONObjectWithData:input options:0 error:nil];
        if (![obj isKindOfClass:[NSDictionary class]]) fail(@"INVALID_INPUT");
        NSString *op = obj[@"op"], *account = obj[@"account"];
        if (![@[@"load", @"store", @"delete", @"audit"] containsObject:op] ||
            ![@[@"session-v1", @"selftest-v1"] containsObject:account]) fail(@"INVALID_INPUT");
        NSSet *keys = [NSSet setWithArray:[obj allKeys]];
        NSSet *expected = [NSSet setWithArray:[op isEqual:@"store"] ? @[@"op", @"account", @"value"] : @[@"op", @"account"]];
        if (![keys isEqual:expected]) fail(@"INVALID_INPUT");

        // Per-process policy only: do not unlock or show unexpected permission UI.
        check(SecKeychainSetUserInteractionAllowed(false));
        NSString *path = [NSHomeDirectory() stringByAppendingPathComponent:@"Library/Keychains/login.keychain-db"];
        SecKeychainRef kc = NULL;
        check(SecKeychainOpen(path.fileSystemRepresentation, &kc));
        SecKeychainStatus kcStatus = 0;
        check(SecKeychainGetStatus(kc, &kcStatus));
        if (!(kcStatus & kSecUnlockStateStatus)) fail(@"SESSION_LOCKED");
        NSDictionary *query = @{
            (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
            (__bridge id)kSecAttrService: service,
            (__bridge id)kSecAttrAccount: account,
            (__bridge id)kSecMatchSearchList: @[(__bridge id)kc]
        };
        if ([op isEqual:@"load"]) {
            NSMutableDictionary *q = [query mutableCopy];
            q[(__bridge id)kSecReturnData] = @YES;
            q[(__bridge id)kSecMatchLimit] = (__bridge id)kSecMatchLimitOne;
            CFTypeRef result = NULL;
            check(SecItemCopyMatching((__bridge CFDictionaryRef)q, &result));
            NSData *data = CFBridgingRelease(result);
            if (![data isKindOfClass:[NSData class]] || data.length > 32768) fail(@"STORE_ERROR");
            id value = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if (![value isKindOfClass:[NSDictionary class]]) fail(@"STORE_ERROR");
            reply(@{@"status": @"OK", @"value": value});
        }
        if ([op isEqual:@"audit"]) {
            NSMutableDictionary *q = [query mutableCopy];
            q[(__bridge id)kSecReturnRef] = @YES;
            q[(__bridge id)kSecMatchLimit] = (__bridge id)kSecMatchLimitOne;
            CFTypeRef item = NULL;
            check(SecItemCopyMatching((__bridge CFDictionaryRef)q, &item));
            SecAccessRef access = NULL;
            check(SecKeychainItemCopyAccess((SecKeychainItemRef)item, &access));
            CFArrayRef acls = SecAccessCopyMatchingACLList(access, kSecACLAuthorizationDecrypt);
            BOOL narrow = acls && CFArrayGetCount(acls) > 0;
            for (CFIndex i = 0; acls && i < CFArrayGetCount(acls); i++) {
                CFArrayRef apps = NULL;
                CFStringRef description = NULL;
                SecKeychainPromptSelector selector = 0;
                check(SecACLCopyContents((SecACLRef)CFArrayGetValueAtIndex(acls, i), &apps, &description, &selector));
                if (!apps || CFArrayGetCount(apps) != 1) narrow = NO;
                if (apps) CFRelease(apps);
                if (description) CFRelease(description);
            }
            if (acls) CFRelease(acls);
            CFRelease(access); CFRelease(item);
            reply(@{@"status": @"OK", @"value": @{@"file_based_local": @YES, @"single_trusted_app": @(narrow)}});
        }
        if ([op isEqual:@"delete"]) {
            OSStatus status = SecItemDelete((__bridge CFDictionaryRef)query);
            if (status != errSecItemNotFound) check(status);
            reply(@{@"status": @"OK"});
        }
        id value = obj[@"value"];
        if (![value isKindOfClass:[NSDictionary class]]) fail(@"INVALID_INPUT");
        NSData *data = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingSortedKeys error:nil];
        if (!data || data.length > 32768) fail(@"INVALID_INPUT");
        OSStatus updated = SecItemUpdate((__bridge CFDictionaryRef)query,
            (__bridge CFDictionaryRef)@{(__bridge id)kSecValueData: data});
        if (updated == errSecItemNotFound) {
            // NULL trusted list means only this signed executable for restricted operations.
            SecAccessRef access = NULL;
            check(SecAccessCreate(CFSTR("Foot Traffic Tapo Session"), NULL, &access));
            NSDictionary *attrs = @{
                (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
                (__bridge id)kSecAttrService: service,
                (__bridge id)kSecAttrAccount: account,
                (__bridge id)kSecUseKeychain: (__bridge id)kc,
                (__bridge id)kSecAttrAccess: (__bridge id)access,
                (__bridge id)kSecValueData: data
            };
            // No synchronizable/data-protection flag: exact local file backend.
            check(SecItemAdd((__bridge CFDictionaryRef)attrs, NULL));
            CFRelease(access);
        } else check(updated);
        CFRelease(kc);
        reply(@{@"status": @"OK"});
    }
}
